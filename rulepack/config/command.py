import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rulepack.config.project_paths import CONFIG_FILE_NAME
from rulepack.config.resolve import flatten, resolve_config
from rulepack.config.settings import ResolvedConfig


def display_value(value: Any, root: Path) -> Any:
    if isinstance(value, list):
        return [display_value(item, root) for item in value]
    if isinstance(value, dict):
        return {key: display_value(item, root) for key, item in value.items()}
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
