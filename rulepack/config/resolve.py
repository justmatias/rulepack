import tomllib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from rulepack.config.project_paths import find_config_path, find_git_root
from rulepack.config.settings import ProjectConfig, ResolvedConfig, Source

# Keys whose values are paths (or lists of paths) relative to the config file.
PATH_KEYS = {
    "sgconfig",
    "importlinter",
}


class ConfigError(Exception):
    pass


def read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: invalid TOML ({error})") from error


def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
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


def resolve_config(
    overrides: dict[str, Any] | None = None, start: Path | None = None
) -> ResolvedConfig:
    """Merge built-in defaults, the repo config and flags, in that order.

    `overrides` maps dotted keys (`sgconfig`, `scan.exclude`) to flag values;
    None means the flag was not given. Flag paths resolve against the current
    directory, file and default paths against the config file's directory.
    """
    current_directory = Path.cwd()
    start = (start or current_directory).resolve()
    git_root = find_git_root(start)
    config_file = find_config_path(start, git_root)
    file_data = read_toml(config_file) if config_file else {}
    root = config_file.parent if config_file else (git_root or start)

    file_values = flatten(
        validate(file_data, str(config_file)).model_dump(exclude_unset=True)
    )
    merged = flatten(ProjectConfig().model_dump())
    sources: dict[str, Source] = dict.fromkeys(merged, "default")
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
        values=validate(unflatten(merged), "resolved config"),
        sources=sources,
    )
