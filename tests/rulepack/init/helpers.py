from pathlib import Path


def read_tree(repository: Path) -> dict[str, str]:
    return {
        path.relative_to(repository).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(repository.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(repository).parts
    }
