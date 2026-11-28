from pathlib import Path

from rulepack.config import ConfigError, GitSource, PackSource, ResolvedConfig
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


def resolve_source_root(name: str, source: PackSource, lock: Lock) -> Path:
    """The source's folder: the path itself, or the locked commit in the cache."""
    if not isinstance(source, GitSource):
        return source.path
    entry = find_locked_entry(name, source, lock)
    return fetch_commit(entry.git, entry.commit)


def lock_sources(config: ResolvedConfig, update: set[str]) -> Lock:
    """Pin every git source: keep unchanged pins, re-resolve the ones in `update`."""
    previous = read_lock(config.lock_file)
    lock = Lock()
    for name, source in sorted(config.values.sources.items()):
        if not isinstance(source, GitSource):
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
