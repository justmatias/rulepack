import argparse
import importlib.metadata
import importlib.resources
import json
import logging
import re
import sys
from pathlib import Path
from typing import Literal

import yaml

from rulepack.config import CONFIG_FILE_NAME, StrictModel
from rulepack.config.project_paths import find_git_root
from rulepack.lint.command import main as run_lint
from rulepack.packs.command import main as run_packs
from rulepack.packs.lock import BARE_KEY

logger = logging.getLogger(__name__)

Action = Literal["create", "append", "exists, skipped"]
RULEPACK_REPOSITORY = "https://github.com/justmatias/rulepack"
PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"
WORKFLOW = Path(".github/workflows/rulepack.yml")
DEFAULT_CHECKS_DIR = "lint"
MAKEFILE_TARGET = re.compile(r"^(?P<target>[A-Za-z0-9_.-]+)\s*:(?!=)", re.MULTILINE)
TOP_LEVEL_KEY = re.compile(r"^[^\s#-][^:]*:")
LIST_ITEM = re.compile(r"^(?P<indent>\s*)-\s")


class InitError(Exception):
    pass


class SourceArgument(StrictModel):
    name: str
    git: str
    ref: str


class PlannedFile(StrictModel):
    path: Path
    action: Action
    # The file's full content after the change; empty when skipped.
    content: str = ""


class ReposInsertionPoint(StrictModel):
    line_index: int
    item_indent: str


def read_rulepack_version() -> str:
    return importlib.metadata.version("rulepack")


def render_template(name: str, **values: str) -> str:
    text = (
        importlib.resources
        .files("rulepack.init")
        .joinpath("templates", name)
        .read_text(encoding="utf-8")
    )
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def plan_new_file(path: Path, content: str) -> PlannedFile:
    if path.exists():
        return PlannedFile(path=path, action="exists, skipped")
    return PlannedFile(path=path, action="create", content=content)


def render_sources(sources: list[SourceArgument]) -> str:
    """An empty `packs` selection and a `[sources]` table per source."""
    if not sources:
        return ""
    tables = "".join(
        f"\n[sources.{source.name}]\ngit = {json.dumps(source.git)}\n"
        f"ref = {json.dumps(source.ref)}\n"
        for source in sources
    )
    return (
        '# Select packs as "<source>/<pack>"; `rulepack packs list` shows them.\n'
        f"packs = []\n{tables}\n"
    )


def plan_layout(
    root: Path, checks_dir: str | None, sources: list[SourceArgument]
) -> list[PlannedFile]:
    """The config, plus a local checks folder when the repo keeps its own checks."""
    local_checks = f'sgconfig = "{checks_dir}/sgconfig.yml"\n\n' if checks_dir else ""
    config = plan_new_file(
        root / CONFIG_FILE_NAME,
        render_template(
            "rulepack.toml",
            sources=render_sources(sources),
            local_checks=local_checks,
        ),
    )
    if checks_dir is None:
        return [config]
    checks = root / checks_dir
    return [
        config,
        plan_new_file(checks / "sgconfig.yml", render_template("sgconfig.yml")),
        plan_new_file(checks / "rules" / ".gitkeep", ""),
        plan_new_file(checks / "rule-tests" / ".gitkeep", ""),
    ]


def find_repos_insertion_point(lines: list[str]) -> ReposInsertionPoint:
    """Where the rulepack entry goes in `repos:` and the indent its items use."""
    start = next(
        (index for index, line in enumerate(lines) if re.match(r"^repos:\s*$", line)),
        None,
    )
    if start is None:
        raise InitError(f"{PRE_COMMIT_CONFIG} has no top-level 'repos:' list")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if TOP_LEVEL_KEY.match(lines[index])
        ),
        len(lines),
    )
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    indent = next(
        (
            match["indent"]
            for line in lines[start + 1 : end]
            if (match := LIST_ITEM.match(line))
        ),
        "  ",
    )
    return ReposInsertionPoint(line_index=end, item_indent=indent)


def append_pre_commit_entry(text: str, entry: str) -> str:
    lines = text.splitlines()
    insertion = find_repos_insertion_point(lines)
    end = insertion.line_index
    block = [
        f"{insertion.item_indent}{line}" if line else line
        for line in entry.splitlines()
    ]
    updated = "\n".join([*lines[:end], *block, *lines[end:]]) + "\n"
    try:
        before = (yaml.safe_load(text) or {}).get("repos") or []
    except yaml.YAMLError as error:
        raise InitError(f"{PRE_COMMIT_CONFIG} is not valid YAML: {error}") from error
    after = (yaml.safe_load(updated) or {}).get("repos") or []
    if len(after) != len(before) + 1 or after[: len(before)] != before:
        raise InitError(f"could not append the rulepack hooks to {PRE_COMMIT_CONFIG}")
    return updated


def plan_pre_commit(root: Path, version: str) -> PlannedFile:
    path = root / PRE_COMMIT_CONFIG
    entry = render_template("pre-commit.yaml", version=version)
    if not path.is_file():
        indented = "".join(f"  {line}\n" for line in entry.splitlines())
        return PlannedFile(path=path, action="create", content=f"repos:\n{indented}")
    text = path.read_text(encoding="utf-8")
    if RULEPACK_REPOSITORY in text:
        return PlannedFile(path=path, action="exists, skipped")
    return PlannedFile(
        path=path, action="append", content=append_pre_commit_entry(text, entry)
    )


def plan_workflow(root: Path, version: str) -> PlannedFile:
    return plan_new_file(
        root / WORKFLOW, render_template("workflow.yml", version=version)
    )


def split_makefile_blocks() -> dict[str, str]:
    """The snippet's blocks (separated by blank lines), by the target they define."""
    blocks = render_template("Makefile.snippet").strip().split("\n\n")
    return {
        match["target"]: block
        for block in blocks
        if (match := MAKEFILE_TARGET.search(block.replace(".PHONY:", "")))
    }


def plan_makefile(root: Path) -> PlannedFile:
    path = root / "Makefile"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    defined = {match["target"] for match in MAKEFILE_TARGET.finditer(text)}
    missing = [
        block
        for target, block in split_makefile_blocks().items()
        if target not in defined
    ]
    if not missing:
        return PlannedFile(path=path, action="exists, skipped")
    separator = "\n" if text and not text.endswith("\n") else ""
    prefix = f"{text}{separator}\n" if text else ""
    return PlannedFile(
        path=path,
        action="append" if text else "create",
        content=prefix + "\n\n".join(missing) + "\n",
    )


def find_existing_layout(root: Path) -> Path | None:
    candidates = (root / CONFIG_FILE_NAME, root / DEFAULT_CHECKS_DIR / "sgconfig.yml")
    return next((path for path in candidates if path.is_file()), None)


def build_plan(root: Path, arguments: argparse.Namespace) -> list[PlannedFile]:
    plan: list[PlannedFile] = []
    if existing := find_existing_layout(root):
        logger.info(
            "init: %s already exists; the layout is left as it is, only missing "
            "optional pieces are added",
            existing.relative_to(root),
        )
    else:
        plan.extend(plan_layout(root, choose_checks_dir(arguments), arguments.source))
    version = read_rulepack_version()
    if arguments.pre_commit:
        plan.append(plan_pre_commit(root, version))
    if arguments.ci == "github":
        plan.append(plan_workflow(root, version))
    if arguments.makefile:
        plan.append(plan_makefile(root))
    return plan


def show_plan(plan: list[PlannedFile], root: Path) -> None:
    for planned in plan:
        logger.info("  %-16s %s", planned.action, planned.path.relative_to(root))


def ask_yes_no(question: str) -> bool:
    sys.stderr.write(f"{question} [y/N] ")
    sys.stderr.flush()
    return sys.stdin.readline().strip().lower() in {"y", "yes"}


def choose_checks_dir(arguments: argparse.Namespace) -> str | None:
    """--checks-dir, or the person's answer when nobody passed it.

    Only a person at a terminal is asked; --yes, --dry-run, scripts and agents get
    the default, a repo that keeps its checks elsewhere.
    """
    checks_dir: str | None = arguments.checks_dir
    can_ask = sys.stdin.isatty() and not arguments.yes and not arguments.dry_run
    if checks_dir is not None or not can_ask:
        return checks_dir
    keeps_own_checks = ask_yes_no(
        f"Keep this repo's own checks in {DEFAULT_CHECKS_DIR}/?"
    )
    return DEFAULT_CHECKS_DIR if keeps_own_checks else None


def write_plan(plan: list[PlannedFile]) -> None:
    for planned in plan:
        if planned.action == "exists, skipped":
            continue
        planned.path.parent.mkdir(parents=True, exist_ok=True)
        planned.path.write_text(planned.content, encoding="utf-8")


def parse_relative_folder(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError(f"'{value}' must be a folder inside the repo")
    return path.as_posix()


def parse_source_argument(value: str) -> SourceArgument:
    name, separator, location = value.partition("=")
    git, at, ref = location.rpartition("@")
    if not (separator and at and git and ref) or not BARE_KEY.fullmatch(name):
        raise argparse.ArgumentTypeError(
            f"'{value}' must look like <name>=<git url>@<ref>, "
            "with a name of letters, digits, '-' or '_'"
        )
    return SourceArgument(name=name, git=git, ref=ref)


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rulepack init",
        description=(
            "Scaffold the rules-as-checks layout: .rulepack.toml, and with "
            "--checks-dir an ast-grep sgconfig with empty rules/ and rule-tests/. "
            "Shows the plan and waits for confirmation; never overwrites a file."
        ),
    )
    parser.add_argument(
        "--checks-dir",
        type=parse_relative_folder,
        help=(
            "Keep this repo's own checks in this folder (for example lint). "
            "Without it, the repo only consumes checks kept elsewhere."
        ),
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help=f"Add the rulepack hooks to {PRE_COMMIT_CONFIG}, pinned to this version.",
    )
    parser.add_argument(
        "--ci",
        choices=["github"],
        help=f"Write {WORKFLOW.as_posix()}, which runs the rulepack action.",
    )
    parser.add_argument(
        "--makefile",
        action="store_true",
        help="Add lint-rules and lint-rules-changed targets to the Makefile.",
    )
    parser.add_argument(
        "--source",
        type=parse_source_argument,
        action="append",
        default=[],
        metavar="NAME=URL@REF",
        help=(
            "Declare a pack source in the new .rulepack.toml and lock it in "
            "rulepack.lock. Repeatable."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the plan and write nothing."
    )
    parser.add_argument(
        "--yes", action="store_true", help="Write without asking for confirmation."
    )
    arguments = parser.parse_args(argv)
    names = [source.name for source in arguments.source]
    if duplicates := sorted({name for name in names if names.count(name) > 1}):
        parser.error(f"--source names must be unique: {', '.join(duplicates)}")
    return arguments


def main(argv: list[str] | None = None) -> int:
    """`rulepack init`: scaffold the rules-as-checks layout in any repo.

    It shows every file it would write and waits for confirmation. It never overwrites
    a file: it creates missing ones, and appends to `.pre-commit-config.yaml` and the
    `Makefile` only when the rulepack entries are not there yet, so a second run changes
    nothing.
    """
    arguments = parse_arguments(argv)
    current_directory = Path.cwd().resolve()
    root = find_git_root(current_directory) or current_directory
    try:
        plan = build_plan(root, arguments)
    except InitError as error:
        logger.error("rulepack init: %s", error)
        return 2
    logger.info("init: plan for %s", root)
    show_plan(plan, root)
    has_files_to_write = any(planned.action != "exists, skipped" for planned in plan)
    if not has_files_to_write and not arguments.source:
        logger.info("init: nothing to write")
        return 0
    if arguments.dry_run:
        logger.info("init: dry run, nothing written")
        return 0
    if has_files_to_write:
        if not arguments.yes and not ask_yes_no("Write these files?"):
            logger.info("init: nothing written")
            return 1
        write_plan(plan)
    if arguments.source:
        # `packs lock` keeps pins it already has, so a rerun after a failed fetch
        # finishes the lock instead of skipping it.
        logger.info("init: locking the sources in rulepack.lock")
        if run_packs(["lock"]) != 0:
            return 1
    logger.info("init: done; running rulepack lint on the new layout")
    return run_lint([])
