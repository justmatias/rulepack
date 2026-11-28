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

LOCK_COMMAND = "run `rulepack packs lock`"


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


def resolve_source_root(name: str, source: PackSource, lock: Lock) -> Path:
    return resolve_source(name, source, lock).root


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
