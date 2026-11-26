import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rulepack.project_paths import CONFIG_FILE_NAME, find_config_path, find_git_root

# Keys whose values are paths (or lists of paths) relative to the config file.
PATH_KEYS = {
    "sgconfig",
    "importlinter",
}

Source = Literal["default", "file", "flag"]


class ConfigError(Exception):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScanSettings(StrictModel):
    exclude: list[str] = []
    extensions: list[str] = [".py"]


class ChangedSettings(StrictModel):
    base_ref: str = "origin/main"


class HookSettings(StrictModel):
    enabled: bool = True
    timeout: float = Field(default=10.0, gt=0, allow_inf_nan=False)


class ProjectConfig(StrictModel):
    sgconfig: Path = Path("lint-rules/sgconfig.yml")
    importlinter: Path = Path(".importlinter")
    scan: ScanSettings = ScanSettings()
    hooks: HookSettings = HookSettings()
    changed: ChangedSettings = ChangedSettings()


class ResolvedConfig(StrictModel):
    """The merged config. Every path value is absolute."""

    root: Path
    git_root: Path | None
    file: Path | None
    values: ProjectConfig
    sources: dict[str, Source]


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


def display_value(value: Any, root: Path) -> Any:
    if isinstance(value, list):
        return [display_value(item, root) for item in value]
    if isinstance(value, Path):
        return (
            value.relative_to(root).as_posix()
            if value.is_relative_to(root)
            else str(value)
        )
    return value


def describe(config: ResolvedConfig) -> dict[str, Any]:
    values = flatten(config.values.model_dump())
    return {
        "file": str(config.file) if config.file else None,
        "root": str(config.root),
        "settings": {
            key: {
                "value": display_value(value, config.root),
                "source": config.sources[key],
            }
            for key, value in values.items()
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rulepack config",
        description=(
            f"Print the resolved project config ({CONFIG_FILE_NAME}) and where "
            "each value comes from."
        ),
    )
    parser.add_argument("--sgconfig", type=Path)
    parser.add_argument("--importlinter", type=Path)
    parser.add_argument(
        "--json", action="store_true", help="Print the resolved config as JSON."
    )
    arguments = parser.parse_args(argv)

    description = describe(
        resolve_config({
            "sgconfig": arguments.sgconfig,
            "importlinter": arguments.importlinter,
        })
    )
    if arguments.json:
        sys.stdout.write(json.dumps(description, indent=2) + "\n")
        return 0
    lines = [
        f"# file: {description['file'] or 'none (built-in defaults)'}",
        f"# root: {description['root']}",
    ]
    lines.extend(
        f"{key} = {json.dumps(setting['value'])}  # {setting['source']}"
        for key, setting in description["settings"].items()
    )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0
