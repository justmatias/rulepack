from pathlib import Path

from rulepack.config import (
    ConfigError,
    GitSource,
    PackSource,
    ResolvedConfig,
    StrictModel,
)
from rulepack.packs.fetch import fetch_commit, resolve_ref
from rulepack.packs.lock import Lock, LockEntry, read_lock
from rulepack.packs.manifest import Manifest, load_manifest

LOCK_COMMAND = "run `rulepack packs lock`"


class Pack(StrictModel):
    source: str
    name: str
    checks: list[Path]
    tests_dir: Path


def find_locked_entry(name: str, source: GitSource, lock: Lock) -> LockEntry:
    entry = lock.sources.get(name)
    if entry is None:
        raise ConfigError(f"source {name!r} is not in the lock; {LOCK_COMMAND}")
    if not entry.matches(source):
        raise ConfigError(
            f"source {name!r} changed since it was locked "
            f"({entry.git}@{entry.ref}); {LOCK_COMMAND}"
        )
    return entry


class ResolvedSource(StrictModel):
    root: Path
    commit: str | None = None


def resolve_source(name: str, source: PackSource, lock: Lock) -> ResolvedSource:
    if not isinstance(source, GitSource):
        return ResolvedSource(root=source.path)
    entry = find_locked_entry(name, source, lock)
    return ResolvedSource(
        root=fetch_commit(entry.git, entry.commit), commit=entry.commit
    )


def lock_sources(
    config: ResolvedConfig, update: set[str], *, selected_only: bool = False
) -> Lock:
    """Pin every git source: keep unchanged pins, re-resolve the ones in `update`."""
    previous = read_lock(config.lock_file)
    lock = Lock(sources=previous.sources.copy()) if selected_only else Lock()
    for name, source in sorted(config.values.sources.items()):
        if not isinstance(source, GitSource):
            continue
        if selected_only and name not in update:
            continue
        entry = previous.sources.get(name)
        if entry is None or not entry.matches(source) or name in update:
            entry = LockEntry(
                git=source.git,
                ref=source.ref,
                commit=resolve_ref(source.git, source.ref),
            )
        fetch_commit(entry.git, entry.commit)
        lock.sources[name] = entry
    return lock


def build_pack(source: str, name: str, manifest: Manifest) -> Pack:
    if name not in manifest.packs:
        raise ConfigError(f"source {source!r} has no pack {name!r}")
    checks = [
        manifest.checks_dir / f"{check}.yml" for check in manifest.packs[name].checks
    ]
    for path in checks:
        if not path.is_file():
            raise ConfigError(f"pack '{source}/{name}' is missing {path}")
    return Pack(source=source, name=name, checks=checks, tests_dir=manifest.tests_dir)


def group_selected_packs(config: ResolvedConfig) -> dict[str, list[str]]:
    """The selected `<source>/<pack>` names grouped by source, in config order."""
    by_source: dict[str, list[str]] = {}
    for selected in dict.fromkeys(config.values.packs):
        source, separator, name = selected.partition("/")
        if not separator or not name or "/" in name:
            raise ConfigError(f"pack {selected!r}: select packs as '<source>/<pack>'")
        if source not in config.values.sources:
            raise ConfigError(f"pack {selected!r}: no source named {source!r}")
        by_source.setdefault(source, []).append(name)
    return by_source


def load_packs(config: ResolvedConfig) -> list[Pack]:
    """The selected packs, fetching a locked commit the cache does not hold."""
    by_source = group_selected_packs(config)
    if not by_source:
        return []
    lock = read_lock(config.lock_file)
    packs: list[Pack] = []
    for source, names in by_source.items():
        resolved = resolve_source(source, config.values.sources[source], lock)
        manifest = load_manifest(resolved.root)
        packs.extend(build_pack(source, name, manifest) for name in names)
    return packs
