import argparse
import hashlib
import json
import logging
import subprocess
import sys
import tempfile
import time
from enum import IntEnum
from pathlib import Path

from pydantic import TypeAdapter

from rulepack.config import ConfigError, ResolvedConfig, resolve_config
from rulepack.config.project_paths import find_config_path, find_git_root
from rulepack.hook.payload import HookPayload
from rulepack.lint.command import ScanFinding, StepResult, select_files

logger = logging.getLogger(__name__)


class HookExit(IntEnum):
    QUIET = 0
    # Agents show a hook's stderr to the model when it exits 2.
    REPORT = 2


def run_lint(root: Path, arguments: list[str], timeout: float) -> dict[str, StepResult]:
    command = [sys.executable, "-P", "-m", "rulepack", "lint", "--json", *arguments]
    # Files let a timed-out lint process return without waiting for a child's pipes.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        completed = subprocess.run(
            command,
            cwd=root,
            stdout=output,
            stderr=errors,
            timeout=timeout,
            check=False,
        )
        # `rulepack lint` exits 1 when a check fails, and higher when it cannot run.
        if completed.returncode > 1:
            errors.seek(0)
            raise RuntimeError(errors.read().decode("utf-8", errors="replace").strip())
        output.seek(0)
        return TypeAdapter(dict[str, StepResult]).validate_json(output.read())


def format_finding(finding: ScanFinding | str) -> str:
    if isinstance(finding, str):
        return finding
    return f"{finding.file}:{finding.line}: {finding.rule}: {finding.message}"


def list_findings(results: dict[str, StepResult]) -> list[str]:
    return sorted({
        format_finding(finding)
        for step, result in results.items()
        if not result.ok
        for finding in result.findings or [f"{step} failed"]
    })


def resolve_hook_config(start: Path) -> ResolvedConfig | None:
    """The project's config, when it has a config file that leaves hooks enabled."""
    config = resolve_config(start=start)
    hooks_enabled = config.file is not None and config.values.hooks.enabled
    return config if hooks_enabled else None


def lint_within_budget(
    config: ResolvedConfig, arguments: list[str], started: float
) -> list[str]:
    """Lint with what is left of the hook's time budget, which starts at `started`."""
    budget = config.values.hooks.timeout
    remaining = budget - (time.monotonic() - started)
    if remaining <= 0:
        raise subprocess.TimeoutExpired("rulepack lint", budget)
    return list_findings(run_lint(config.root, arguments, remaining))


def find_edited_file_findings(
    root: Path, edited: list[Path], started: float
) -> list[str]:
    config = resolve_hook_config(root)
    if config is None:
        return []
    files = select_files(config, edited)
    if not files:
        return []
    arguments = ["--files", *[str(path) for path in files], "--only", "scan"]
    return lint_within_budget(config, arguments, started)


def find_stop_marker_path(root: Path, session: str) -> Path:
    """The temp file that holds the digest of the findings a session's stop reported."""
    key = hashlib.sha256(json.dumps([str(root), session]).encode()).hexdigest()
    return Path(tempfile.gettempdir()) / f"rulepack-stop-{key}"


def find_new_stop_findings(directory: Path, session: str, started: float) -> list[str]:
    """The changed files' findings, unless this session's last stop reported them."""
    config = resolve_hook_config(directory)
    if config is None:
        return []
    findings = lint_within_budget(config, ["--changed", "--only", "scan"], started)
    marker = find_stop_marker_path(config.root, session)
    if not findings:
        marker.unlink(missing_ok=True)
        return []
    digest = hashlib.sha256(json.dumps(findings).encode()).hexdigest().encode()
    if marker.is_file() and marker.read_bytes() == digest:
        return []
    with tempfile.NamedTemporaryFile(
        dir=marker.parent, delete_on_close=False
    ) as pending:
        pending.write(digest)
        pending.close()
        Path(pending.name).replace(marker)
    return findings


def group_paths_by_project(
    directory: Path, paths: list[Path]
) -> dict[Path, list[Path]]:
    """The edited paths inside the workspace, keyed by the project config's folder."""
    workspace = find_git_root(directory) or directory
    projects: dict[Path, list[Path]] = {}
    for path in paths:
        if not path.is_relative_to(workspace):
            continue
        git_root = find_git_root(path.parent)
        start = path.parent if git_root else directory
        config = find_config_path(start, git_root)
        if config and path.is_relative_to(config.parent):
            projects.setdefault(config.parent, []).append(path)
    return projects


def find_post_edit_findings(payload: HookPayload, started: float) -> list[str]:
    directory = payload.resolve_directory()
    projects = group_paths_by_project(directory, payload.list_edited_paths(directory))
    return [
        finding
        for root, paths in projects.items()
        for finding in find_edited_file_findings(root, paths, started)
    ]


def find_event_findings(event: str, payload: HookPayload, started: float) -> list[str]:
    if event == "post-edit":
        return find_post_edit_findings(payload, started)
    return find_new_stop_findings(
        payload.resolve_directory(), payload.session_id, started
    )


def main(argv: list[str] | None = None) -> int:
    """Write the event's findings to stderr; a check that cannot run stays quiet."""
    started = time.monotonic()
    parser = argparse.ArgumentParser(
        prog="rulepack hook", description="Run checks for agent edits and stops."
    )
    parser.add_argument("event", choices=("post-edit", "stop"))
    event = parser.parse_args(argv).event
    try:
        payload = HookPayload.model_validate_json(sys.stdin.read())
        findings = find_event_findings(event, payload, started)
    except subprocess.TimeoutExpired:
        logger.warning("rulepack hook: timed out (time budget exhausted)")
        return HookExit.QUIET
    except (ConfigError, OSError, RuntimeError, ValueError) as error:
        logger.warning("rulepack hook: %s", error)
        return HookExit.QUIET
    if not findings:
        return HookExit.QUIET
    sys.stderr.write("\n".join(findings) + "\n")
    return HookExit.REPORT
