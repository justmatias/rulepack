import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def try_repo(
    repository: Path, source: str, *hook_id: str
) -> subprocess.CompletedProcess:
    (repository / "module.py").write_text(source)
    subprocess.run(["git", "add", "--all"], cwd=repository, check=True)
    return subprocess.run(
        ["pre-commit", "try-repo", str(REPOSITORY_ROOT), *hook_id, "--all-files"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
