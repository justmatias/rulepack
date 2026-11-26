import argparse
import fnmatch
import json
import logging
import os
import shutil
import subprocess
import sys
import sysconfig
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field

from rulepack.config import ConfigError, ResolvedConfig, StrictModel, resolve_config
from rulepack.lint.changed_files import ChangedFilesError, changed_files

logger = logging.getLogger(__name__)

STEPS = ("test", "scan", "imports")
Mode = Literal["full", "changed", "files"]


class LintError(Exception):
    pass


class StepResult(StrictModel):
    ok: bool
    skipped: str | None = None
    findings: list[Any] = Field(default_factory=list)


class LintRun(StrictModel):
    """What one `rulepack lint` invocation scans and how it reports."""

    config: ResolvedConfig
    mode: Mode = "full"
    files: list[Path] = Field(default_factory=list)
    json_output: bool = False


def find_tool(name: str) -> str:
    """The tool installed with rulepack wins over whatever is on PATH."""
    directories = [Path(sysconfig.get_path("scripts")), Path(sys.executable).parent]
    for directory in directories:
        for candidate in (directory / name, directory / f"{name}.exe"):
            if candidate.is_file():
                return str(candidate)
    if found := shutil.which(name):
        return found
    raise LintError(
        f"'{name}' was not found next to {sys.executable} or on PATH; "
        "reinstall rulepack (uv tool install --editable <checkout>)"
    )


def run_tool(
    command: list[str], run: LintRun, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    logger.debug("lint: %s", " ".join(command))
    return subprocess.run(
        command,
        cwd=run.config.root,
        capture_output=run.json_output,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )


def output_lines(completed: subprocess.CompletedProcess) -> list[str]:
    return [
        line
        for line in f"{completed.stdout or ''}{completed.stderr or ''}".splitlines()
        if line.strip()
    ]


def tool_result(completed: subprocess.CompletedProcess) -> StepResult:
    ok = completed.returncode == 0
    return StepResult(ok=ok, findings=[] if ok else output_lines(completed))


def sgconfig_path(run: LintRun) -> Path:
    path = run.config.values.sgconfig
    if not path.is_file():
        raise LintError(
            f"no ast-grep config at {path} (set sgconfig in .rulepack.toml)"
        )
    return path


def has_rule_tests(sgconfig: Path) -> bool:
    data = yaml.safe_load(sgconfig.read_text(encoding="utf-8")) or {}
    test_directories = [
        sgconfig.parent / entry["testDir"]
        for entry in data.get("testConfigs") or []
        if isinstance(entry, dict) and entry.get("testDir")
    ]
    return any(
        any(directory.glob("*.y*ml"))
        for directory in test_directories
        if directory.is_dir()
    )


def step_test(run: LintRun) -> StepResult:
    sgconfig = sgconfig_path(run)
    if not has_rule_tests(sgconfig):
        return StepResult(ok=True, skipped="the sgconfig has no rule tests")
    command = [find_tool("ast-grep"), "test", "-c", str(sgconfig)]
    return tool_result(run_tool([*command, "--skip-snapshot-tests"], run))


def scan_finding(line: str) -> dict[str, Any]:
    match = json.loads(line)
    return {
        "file": match.get("file"),
        "line": match.get("range", {}).get("start", {}).get("line", 0) + 1,
        "rule": match.get("ruleId"),
        "severity": match.get("severity"),
        "message": match.get("message"),
    }


def scan_targets(run: LintRun) -> list[str]:
    if run.mode == "full":
        excludes = [f"!{pattern}" for pattern in run.config.values.scan.exclude]
        return [argument for glob in excludes for argument in ("--globs", glob)] + ["."]
    return [
        "--error",
        *[os.path.relpath(path, run.config.root) for path in run.files],
    ]


def step_scan(run: LintRun) -> StepResult:
    if run.mode != "full" and not run.files:
        return StepResult(ok=True, skipped="no changed files to scan")
    sgconfig = sgconfig_path(run)
    command = [find_tool("ast-grep"), "scan", "-c", str(sgconfig)]
    if run.json_output:
        command.append("--json=stream")
    completed = run_tool([*command, *scan_targets(run)], run)
    if not run.json_output:
        return StepResult(ok=completed.returncode == 0)
    findings: list[Any] = [
        scan_finding(line) for line in completed.stdout.splitlines() if line
    ]
    if completed.returncode and not findings:
        findings = output_lines(completed)
    return StepResult(ok=completed.returncode == 0, findings=findings)


def project_lint_imports(root: Path) -> list[str] | None:
    """The repo's own lint-imports, when its uv environment provides one."""
    lock_file = root / "uv.lock"
    uv = shutil.which("uv")
    if (
        uv
        and lock_file.is_file()
        and 'name = "import-linter"' in lock_file.read_text(encoding="utf-8")
    ):
        return [uv, "run", "--frozen", "lint-imports"]
    return None


def step_imports(run: LintRun) -> StepResult:
    importlinter = run.config.values.importlinter
    if not importlinter.is_file():
        return StepResult(ok=True, skipped=f"no {importlinter.name}")
    root = run.config.root
    command = project_lint_imports(root)
    env = None
    if command:
        logger.info("lint: imports uses the project's lint-imports (uv run)")
    else:
        logger.info("lint: imports uses the lint-imports bundled with rulepack")
        command = [find_tool("lint-imports")]
        python_path = [str(root), str(root / "src"), os.environ.get("PYTHONPATH", "")]
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(path for path in python_path if path),
        }
    if importlinter.resolve() != (root / ".importlinter").resolve():
        command += ["--config", str(importlinter)]
    return tool_result(run_tool(command, run, env))


STEP_FUNCTIONS: dict[str, Callable[[LintRun], StepResult]] = {
    "test": step_test,
    "scan": step_scan,
    "imports": step_imports,
}


def run_step(name: str, run: LintRun) -> StepResult:
    logger.info("lint: running %s", name)
    try:
        return STEP_FUNCTIONS[name](run)
    except (LintError, ConfigError, subprocess.CalledProcessError) as error:
        logger.error("lint: %s: %s", name, error)
        return StepResult(ok=False, findings=[str(error)])


def run_lint(steps: list[str], run: LintRun) -> dict[str, StepResult]:
    return {name: run_step(name, run) for name in steps}


def selected_steps(only: list[str] | None, skip: list[str] | None) -> list[str]:
    return [
        step
        for step in STEPS
        if (not only or step in only) and step not in (skip or [])
    ]


def is_excluded(path: Path, root: Path, exclude_globs: list[str]) -> bool:
    if not path.is_relative_to(root):
        return False
    relative = path.relative_to(root).as_posix()
    return any(fnmatch.fnmatch(relative, pattern) for pattern in exclude_globs)


def selected_files(config: ResolvedConfig, names: list[str]) -> list[Path]:
    """The given files that exist, have a scanned extension and are not excluded."""
    extensions = config.values.scan.extensions
    files = {Path(name).resolve() for name in names}
    return sorted(
        path
        for path in files
        if path.is_file()
        and path.suffix in extensions
        and not is_excluded(path, config.root.resolve(), config.values.scan.exclude)
    )


def build_run(arguments: argparse.Namespace) -> LintRun:
    config = resolve_config()
    if arguments.files is not None:
        return LintRun(
            config=config,
            mode="files",
            files=selected_files(config, arguments.files),
            json_output=arguments.json,
        )
    if not arguments.changed:
        return LintRun(config=config, json_output=arguments.json)
    if config.git_root is None:
        raise LintError("--changed needs a git repository")
    changed = changed_files(
        config.git_root,
        base_ref=arguments.base_ref,
        default_base_ref=config.values.changed.base_ref,
        staged=arguments.staged,
        extensions=config.values.scan.extensions,
    )
    return LintRun(
        config=config,
        mode="changed",
        files=selected_files(config, [str(path) for path in changed]),
        json_output=arguments.json,
    )


def report(results: dict[str, StepResult], json_output: bool) -> None:
    for name, result in results.items():
        if result.skipped:
            logger.info("lint: %s skipped (%s)", name, result.skipped)
        elif result.ok:
            logger.info("lint: %s OK", name)
        else:
            logger.error("lint: %s FAILED", name)
    if json_output:
        sys.stdout.write(
            json.dumps(
                {name: result.model_dump() for name, result in results.items()},
                indent=2,
            )
            + "\n"
        )


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rulepack lint",
        description=(
            "Run every check in order: ast-grep rule tests, the ast-grep scan "
            "and import-linter. All steps run; the exit code is 1 if any failed."
        ),
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--changed",
        action="store_true",
        help=(
            "Scan only the files changed against the base ref, and fail on "
            "warnings too."
        ),
    )
    selection.add_argument(
        "--files",
        nargs="+",
        metavar="FILE",
        help="Scan exactly these files, and fail on warnings too (for pre-commit).",
    )
    parser.add_argument(
        "--base-ref",
        help="With --changed: compare against this ref (default: [changed].base_ref).",
    )
    parser.add_argument(
        "--staged", action="store_true", help="With --changed: only the staged files."
    )
    parser.add_argument("--only", nargs="+", choices=STEPS, metavar="STEP")
    parser.add_argument("--skip", nargs="+", choices=STEPS, metavar="STEP")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print {step: {ok, skipped, findings}} as JSON.",
    )
    arguments = parser.parse_args(argv)
    if (arguments.base_ref or arguments.staged) and not arguments.changed:
        parser.error("--base-ref and --staged need --changed")
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        run = build_run(arguments)
        steps = selected_steps(arguments.only, arguments.skip)
        results = run_lint(steps, run)
    except (LintError, ConfigError, ChangedFilesError, yaml.YAMLError) as error:
        logger.error("rulepack lint: %s", error)
        return 2
    report(results, run.json_output)
    return 0 if all(result.ok for result in results.values()) else 1
