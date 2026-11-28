import argparse
import json
import logging
import sys

from rulepack.config import (
    ConfigError,
    GitSource,
    ResolvedConfig,
    StrictModel,
    resolve_config,
)
from rulepack.packs.lock import read_lock, write_lock
from rulepack.packs.manifest import load_manifest
from rulepack.packs.sources import lock_sources, resolve_source_root

logger = logging.getLogger(__name__)


class SourceDescription(StrictModel):
    git: str | None = None
    ref: str | None = None
    path: str | None = None
    commit: str | None
    # Each pack's check ids, by pack name.
    packs: dict[str, list[str]]


def describe_sources(config: ResolvedConfig) -> dict[str, SourceDescription]:
    lock = read_lock(config.lock_file)
    described: dict[str, SourceDescription] = {}
    for name, source in sorted(config.values.sources.items()):
        manifest = load_manifest(resolve_source_root(name, source, lock))
        entry = lock.sources.get(name)
        described[name] = SourceDescription(
            **source.model_dump(mode="json"),
            # A source that became a path keeps its old lock entry until relocked.
            commit=entry.commit
            if entry is not None and isinstance(source, GitSource)
            else None,
            packs={
                pack: list(manifest.packs[pack].checks)
                for pack in sorted(manifest.packs)
            },
        )
    return described


def print_sources(described: dict[str, SourceDescription]) -> None:
    for name, source in described.items():
        origin = (
            f"{source.git}@{source.ref} ({source.commit})"
            if source.git
            else source.path
        )
        sys.stdout.write(f"{name}: {origin}\n")
        for pack, checks in source.packs.items():
            sys.stdout.write(f"  {name}/{pack}: {', '.join(checks) or '(no checks)'}\n")


def select_sources_to_update(config: ResolvedConfig, names: list[str]) -> set[str]:
    """The named git sources, or every git source when none is named."""
    git_sources = {
        name
        for name, source in config.values.sources.items()
        if isinstance(source, GitSource)
    }
    selected = set(names) or git_sources
    if unknown := sorted(selected - git_sources):
        raise ConfigError(f"no git source named {', '.join(unknown)}")
    return selected


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rulepack packs",
        description="Pin, update and list the pack sources in .rulepack.toml.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "lock", help="Pin every git source in rulepack.lock and fetch it."
    )
    update = commands.add_parser(
        "update", help="Re-resolve the refs of these sources (default: all)."
    )
    update.add_argument("sources", nargs="*", metavar="SOURCE")
    listing = commands.add_parser("list", help="List every source's packs and checks.")
    listing.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    config = resolve_config()
    if arguments.command == "list":
        described = describe_sources(config)
        if arguments.json:
            payload = {name: source.model_dump() for name, source in described.items()}
            sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        else:
            print_sources(described)
        return 0
    update = (
        select_sources_to_update(config, arguments.sources)
        if arguments.command == "update"
        else set()
    )
    lock = lock_sources(config, update)
    write_lock(config.lock_file, lock)
    logger.info("packs: locked %d source(s) in %s", len(lock.sources), config.lock_file)
    return 0
