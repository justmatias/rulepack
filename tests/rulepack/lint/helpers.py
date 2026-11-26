import subprocess
from pathlib import Path


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def init_git_repository(repository: Path) -> Path:
    git(repository, "init", "--quiet", "--initial-branch=main")
    git(repository, "config", "user.email", "tests@example.invalid")
    git(repository, "config", "user.name", "Tests")
    git(repository, "config", "commit.gpgsign", "false")
    git(repository, "add", "--all")
    git(repository, "commit", "--quiet", "--allow-empty", "-m", "initial")
    return repository


def names(paths: list[Path], repository: Path) -> list[str]:
    return [path.relative_to(repository).as_posix() for path in paths]
