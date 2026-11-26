import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from rulepack.config.project_paths import find_config_path, find_git_root

logger = logging.getLogger(__name__)


def hook_directory(payload: dict) -> Path:
    directory = payload.get("cwd")
    if isinstance(directory, str) and directory:
        return Path(directory).resolve()
    workspaces = payload.get("workspace_roots")
    edited = payload.get("file_path")
    if isinstance(workspaces, list) and isinstance(edited, str):
        path = Path(edited).resolve()
        for workspace in workspaces:
            if isinstance(workspace, str) and path.is_relative_to(
                root := Path(workspace).resolve()
            ):
                return root
    return Path.cwd()


def lint_findings(root: Path, arguments: list[str], timeout: float) -> list[str]:
    import tempfile  # pylint: disable=import-outside-toplevel

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
        output.seek(0)
        errors.seek(0)
        if completed.returncode not in (0, 1):
            raise RuntimeError(errors.read().decode("utf-8", errors="replace").strip())
        results = json.load(output)

    findings = []
    for step, result in results.items():
        if result["ok"]:
            continue
        for finding in result["findings"] or [f"{step} failed"]:
            message = (
                f"{finding['file']}:{finding['line']}: "
                f"{finding['rule']}: {finding['message']}"
                if isinstance(finding, dict)
                else finding
            )
            findings.append(message)
    return sorted(set(findings))


def repeated_stop(root: Path, session: str, findings: list[str]) -> bool:
    import hashlib  # pylint: disable=import-outside-toplevel
    import tempfile  # pylint: disable=import-outside-toplevel

    key = hashlib.sha256(json.dumps([str(root), session]).encode()).hexdigest()
    marker = Path(tempfile.gettempdir()) / f"rulepack-stop-{key}"
    if not findings:
        marker.unlink(missing_ok=True)
        return False
    digest = hashlib.sha256(json.dumps(findings).encode()).hexdigest()
    if marker.is_file() and marker.read_bytes() == digest.encode():
        return True
    with tempfile.NamedTemporaryFile(
        dir=marker.parent, delete_on_close=False
    ) as pending:
        pending.write(digest.encode())
        pending.close()
        Path(pending.name).replace(marker)
    return False


def patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    updating = False
    for line in patch.split("\n"):
        # Leading whitespace in an update hunk marks unchanged file content.
        header, _, path = (line.rstrip() if updating else line.strip()).partition(": ")
        if not path:
            continue
        match header:
            case "*** Update File":
                paths.append(path)
                updating = True
            case "*** Add File":
                paths.append(path)
                updating = False
            case "*** Delete File":
                updating = False
            case "*** Move to" if updating:
                paths[-1] = path
    return paths


def edited_paths(directory: Path, payload: dict) -> list[Path]:
    tool_input = payload.get("tool_input")
    if payload.get("tool_name") == "apply_patch" and isinstance(tool_input, dict):
        patch = tool_input.get("command")
        if isinstance(patch, str):
            return [(directory / path).resolve() for path in patch_paths(patch)]
        return []
    path = (
        tool_input.get("file_path")
        if isinstance(tool_input, dict)
        else payload.get("file_path")
    )
    return [(directory / path).resolve()] if isinstance(path, str) and path else []


def edited_projects(directory: Path, paths: list[Path]) -> dict[Path, list[Path]]:
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


def check_hook(
    directory: Path, edited: list[Path] | None, session: str, started: float
) -> int:
    # Keep the unrelated-repo path free of lint and validation imports.
    # pylint: disable=import-outside-toplevel
    from rulepack.config import ConfigError, resolve_config
    from rulepack.lint.command import select_files

    try:
        config = resolve_config(start=directory)
        settings = config.values.hooks
        if config.file is None or not settings.enabled:
            return 0
        if edited is None:
            arguments = ["--changed", "--only", "scan"]
        else:
            paths = select_files(config, edited)
            if not paths:
                return 0
            arguments = [
                "--files",
                *[str(path) for path in paths],
                "--only",
                "scan",
            ]
        remaining = settings.timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise subprocess.TimeoutExpired("rulepack lint", settings.timeout)
        findings = lint_findings(config.root, arguments, remaining)
        if edited is None and repeated_stop(config.root, session, findings):
            return 0
    except subprocess.TimeoutExpired:
        logger.warning("rulepack hook: timed out (time budget exhausted)")
        return 0
    except (ConfigError, OSError, RuntimeError, ValueError) as error:
        logger.warning("rulepack hook: %s", error)
        return 0
    if findings:
        sys.stderr.write("\n".join(findings) + "\n")
    return 2 if findings else 0


def main(argv: list[str] | None = None) -> int:
    started = time.monotonic()
    parser = argparse.ArgumentParser(
        prog="rulepack hook", description="Run checks for agent edits and stops."
    )
    parser.add_argument("event", choices=("post-edit", "stop"))
    event = parser.parse_args(argv).event
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        directory = hook_directory(payload)
        session = str(payload.get("session_id", ""))
        if event == "post-edit":
            projects = edited_projects(directory, edited_paths(directory, payload))
            return max(
                (
                    check_hook(root, paths, session, started)
                    for root, paths in projects.items()
                ),
                default=0,
            )
        if config := find_config_path(directory, find_git_root(directory)):
            return check_hook(config.parent, None, session, started)
    except (OSError, RuntimeError, ValueError) as error:
        logger.warning("rulepack hook: %s", error)
    return 0
