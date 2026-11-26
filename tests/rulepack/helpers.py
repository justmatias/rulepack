import subprocess
from pathlib import Path


def run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def init_git_repository(repository: Path) -> Path:
    run_git(repository, "init", "--quiet", "--initial-branch=main")
    run_git(repository, "config", "user.email", "tests@example.invalid")
    run_git(repository, "config", "user.name", "Tests")
    run_git(repository, "config", "commit.gpgsign", "false")
    run_git(repository, "add", "--all")
    run_git(repository, "commit", "--quiet", "--allow-empty", "-m", "initial")
    return repository


def list_relative_names(paths: list[Path], repository: Path) -> list[str]:
    return [path.relative_to(repository).as_posix() for path in paths]
