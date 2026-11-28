import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from rulepack.config.project_paths import (
    CONFIG_FILE_NAME,
    LEGACY_CONFIG_FILE_NAME,
    LOCK_FILE_NAME,
    find_config_path,
    find_git_root,
    find_host_config_path,
)
from rulepack.config.settings import HostConfig, ProjectConfig, ResolvedConfig, Source

# Keys whose values are paths (or lists of paths) relative to the config file.
PATH_KEYS = {
    "sgconfig",
    "importlinter",
}
# Values kept whole: their keys are names chosen by the user, not config keys.
OPAQUE_KEYS = {"sources", "pack_overrides.severity"}


class ConfigError(Exception):
    pass


def read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: invalid TOML ({error})") from error


def reject_legacy_config(start: Path, git_root: Path | None) -> None:
    """Fail on an mstack config that still holds lint keys, instead of ignoring it."""
    path = find_config_path(start, git_root, LEGACY_CONFIG_FILE_NAME)
    if path is None:
        return
    lint_keys = sorted(read_toml(path).keys() & ProjectConfig.model_fields.keys())
    if lint_keys:
        raise ConfigError(
            f"{path} sets {', '.join(lint_keys)}, but rulepack reads "
            f"{CONFIG_FILE_NAME}: rename the file to {CONFIG_FILE_NAME}"
        )


def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict) and f"{prefix}{key}" not in OPAQUE_KEYS:
            flat.update(flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def unflatten(flat: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for dotted_key, value in flat.items():
        *parents, leaf = dotted_key.split(".")
        table = data
        for parent in parents:
            table = table.setdefault(parent, {})
        table[leaf] = value
    return data


def absolute(value: Any, base: Path) -> Any:
    if isinstance(value, list):
        return [absolute(item, base) for item in value]
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def validate(data: dict[str, Any], origin: str) -> ProjectConfig:
    try:
        return ProjectConfig.model_validate(data)
    except ValidationError as error:
        raise ConfigError(f"{origin}: {error}") from error


def is_ci() -> bool:
    return os.environ.get("CI", "").lower() in {"true", "1"}


def read_host_config() -> HostConfig | None:
    """This machine's default packs, for repos without a config. CI never reads it."""
    path = find_host_config_path()
    if is_ci() or not path.is_file():
        return None
    try:
        return HostConfig.model_validate(read_toml(path))
    except ValidationError as error:
        raise ConfigError(f"{path}: {error}") from error


def make_source_paths_absolute(sources: dict[str, Any], base: Path) -> dict[str, Any]:
    return {
        name: {**entry, "path": absolute(entry["path"], base)}
        if entry.get("path") is not None
        else entry
        for name, entry in sources.items()
    }


def resolve_config(
    overrides: dict[str, Any] | None = None, start: Path | None = None
) -> ResolvedConfig:
    """Merge built-in defaults, host defaults, the repo config and flags, in order.

    Host defaults (`packs` and `sources`) apply only when the repo has no config.

    `overrides` maps dotted keys (`sgconfig`, `scan.exclude`) to flag values;
    None means the flag was not given. Flag paths resolve against the current
    directory, file and default paths against the config file's directory.
    """
    current_directory = Path.cwd()
    start = (start or current_directory).resolve()
    git_root = find_git_root(start)
    config_file = find_config_path(start, git_root)
    if config_file is None:
        reject_legacy_config(start, git_root)
    file_data = read_toml(config_file) if config_file else {}
    root = config_file.parent if config_file else (git_root or start)

    file_values = flatten(
        validate(file_data, str(config_file)).model_dump(exclude_unset=True)
    )
    merged = flatten(ProjectConfig().model_dump())
    sources: dict[str, Source] = dict.fromkeys(merged, "default")
    lock_file = root / LOCK_FILE_NAME
    host = read_host_config() if config_file is None else None
    if host is not None and host.packs:
        host_directory = find_host_config_path().parent
        merged["packs"] = host.packs
        merged["sources"] = make_source_paths_absolute(
            host.model_dump()["sources"], host_directory
        )
        sources.update({"packs": "host", "sources": "host"})
        lock_file = host_directory / LOCK_FILE_NAME
    if "sources" in file_values:
        file_values["sources"] = make_source_paths_absolute(
            file_values["sources"], root
        )
    merged.update(file_values)
    sources.update(dict.fromkeys(file_values, "file"))
    for key in merged:
        if key in PATH_KEYS:
            merged[key] = absolute(merged[key], root)
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        if key not in merged:
            raise ConfigError(f"unknown config key '{key}'")
        merged[key] = absolute(value, current_directory) if key in PATH_KEYS else value
        sources[key] = "flag"

    return ResolvedConfig(
        root=root,
        git_root=git_root,
        file=config_file,
        lock_file=lock_file,
        values=validate(unflatten(merged), "resolved config"),
        sources=sources,
    )
