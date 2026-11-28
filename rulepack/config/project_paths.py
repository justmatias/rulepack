from pathlib import Path

CONFIG_FILE_NAME = ".rulepack.toml"
# mstack v6 read the same keys from this file.
LEGACY_CONFIG_FILE_NAME = ".mstack.toml"


def find_git_root(start: Path) -> Path | None:
    return next(
        (
            directory
            for directory in (start, *start.parents)
            if (directory / ".git").exists()
        ),
        None,
    )


def candidate_directories(start: Path, git_root: Path | None) -> list[Path]:
    if git_root is None:
        return [start]
    directories = [start]
    for parent in start.parents:
        if not parent.is_relative_to(git_root):
            break
        directories.append(parent)
    return directories


def find_config_path(
    start: Path, git_root: Path | None, name: str = CONFIG_FILE_NAME
) -> Path | None:
    """Find the nearest config without looking above the git root."""
    return next(
        (
            directory / name
            for directory in candidate_directories(start, git_root)
            if (directory / name).is_file()
        ),
        None,
    )
