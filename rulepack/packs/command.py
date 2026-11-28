import argparse
import json
import logging
import sys

from rulepack.config import ConfigError, ResolvedConfig, resolve_config
from rulepack.packs.sources import (
    find_source_root,
    load_manifest,
    lock_sources,
    read_lock,
    write_lock,
)

logger = logging.getLogger(__name__)


def describe_sources(config: ResolvedConfig) -> dict:
    lock = read_lock(config.lock_file)
    described: dict = {}
    for name, source in sorted(config.values.sources.items()):
        root = find_source_root(name, source, lock, fetch=True)
        manifest = load_manifest(root)
        entry = lock.sources.get(name)
        described[name] = {
            "git": source.git,
            "ref": source.ref,
            "path": str(source.path) if source.path else None,
            "commit": entry.commit if entry else None,
            "packs": {
                pack: list(manifest.packs[pack].checks)
                for pack in sorted(manifest.packs)
            },
        }
    return described


def print_sources(described: dict) -> None:
    for name, source in described.items():
        origin = (
            f"{source['git']}@{source['ref']} ({source['commit']})"
            if source["git"]
            else source["path"]
        )
        sys.stdout.write(f"{name}: {origin}\n")
        for pack, checks in source["packs"].items():
            sys.stdout.write(f"  {name}/{pack}: {', '.join(checks) or '(no checks)'}\n")


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="rulepack packs",
        description="Pin, update and list the pack sources in .rulepack.toml.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    lock = commands.add_parser(
        "lock", help="Pin every git source in rulepack.lock and fetch it."
    )
    lock.add_argument(
        "--host",
        action="store_true",
        help="Lock this machine's default sources instead of the repo's.",
    )
    update = commands.add_parser(
        "update", help="Re-resolve the refs of these sources (default: all)."
    )
    update.add_argument("sources", nargs="*", metavar="SOURCE")
    listing = commands.add_parser("list", help="List every source's packs and checks.")
    listing.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """`rulepack packs`: pin, update and list the pack sources."""
    arguments = parse_arguments(argv)
    config = resolve_config()
    if arguments.command == "list":
        described = describe_sources(config)
        if arguments.json:
            sys.stdout.write(json.dumps(described, indent=2) + "\n")
        else:
            print_sources(described)
        return 0
    locks_host_sources = getattr(arguments, "host", False)
    if locks_host_sources and config.sources.get("sources") != "host":
        raise ConfigError(
            "--host locks this machine's default sources, which apply only where "
            "there is no .rulepack.toml; run it outside such a repo"
        )
    update = None
    if arguments.command == "update":
        git_sources = {
            name for name, source in config.values.sources.items() if source.git
        }
        update = set(arguments.sources) or git_sources
        if unknown := sorted(update - git_sources):
            raise ConfigError(f"no git source named {', '.join(unknown)}")
    lock = lock_sources(config, update)
    write_lock(config.lock_file, lock)
    logger.info("packs: locked %d source(s) in %s", len(lock.sources), config.lock_file)
    return 0
