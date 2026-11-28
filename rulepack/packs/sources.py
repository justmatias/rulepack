import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import tomllib
from collections.abc import Callable
from pathlib import Path

from pydantic import Field, ValidationError

from rulepack.config import ConfigError, PackSource, ResolvedConfig, StrictModel

MANIFEST_FILE_NAME = "packs.toml"
LOCK_COMMAND = "run `rulepack packs lock`"
BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


class PacksNotCached(ConfigError):
    """A locked commit is not in the cache, and this run may not fetch it."""


class ManifestPack(StrictModel):
    checks: list[str]


class Manifest(StrictModel):
    checks_dir: Path = Path("lint/rules")
    tests_dir: Path = Path("lint/rule-tests")
    packs: dict[str, ManifestPack] = Field(default_factory=dict)


class LockEntry(StrictModel):
    git: str
    ref: str
    commit: str


class Lock(StrictModel):
    sources: dict[str, LockEntry] = Field(default_factory=dict)


def resolve_inside(root: Path, relative: Path, what: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ConfigError(f"{root / MANIFEST_FILE_NAME}: {what} escapes the source")
    return path


def load_manifest(root: Path) -> Manifest:
    """Read and validate a source's packs.toml; every path stays inside the source."""
    path = root / MANIFEST_FILE_NAME
    if not path.is_file():
        raise ConfigError(f"{root} has no {MANIFEST_FILE_NAME}")
    try:
        manifest = Manifest.model_validate(
            tomllib.loads(path.read_text(encoding="utf-8"))
        )
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise ConfigError(f"{path}: {error}") from error
    checks_dir = resolve_inside(root, manifest.checks_dir, "checks_dir")
    tests_dir = resolve_inside(root, manifest.tests_dir, "tests_dir")
    for name, pack in manifest.packs.items():
        for check in pack.checks:
            resolve_inside(
                checks_dir, Path(f"{check}.yml"), f"pack {name!r} check {check!r}"
            )
    return manifest.model_copy(
        update={"checks_dir": checks_dir, "tests_dir": tests_dir}
    )


def read_lock(path: Path) -> Lock:
    if not path.is_file():
        return Lock()
    try:
        return Lock.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise ConfigError(f"{path}: {error}") from error


def quote_toml_key(name: str) -> str:
    return name if BARE_KEY.fullmatch(name) else json.dumps(name)


def render_lock(lock: Lock) -> str:
    lines = ["# Written by `rulepack packs lock`. Commit this file.", ""]
    for name in sorted(lock.sources):
        entry = lock.sources[name]
        lines += [
            f"[sources.{quote_toml_key(name)}]",
            f"git = {json.dumps(entry.git)}",
            f"ref = {json.dumps(entry.ref)}",
            f"commit = {json.dumps(entry.commit)}",
            "",
        ]
    return "\n".join(lines).rstrip("\n") + "\n"


def write_lock(path: Path, lock: Lock) -> None:
    text = render_lock(lock)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8", suffix=".tmp"
    ) as pending:
        pending.write(text)
    Path(pending.name).replace(path)


def find_cache_directory(url: str) -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    # 16 hex digits keep clone paths under Windows' 260-character limit.
    return base / "rulepack" / "sources" / hashlib.sha256(url.encode()).hexdigest()[:16]


def run_git(*arguments: str, cwd: Path | None = None) -> bytes:
    completed = subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, check=False
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ConfigError(f"git {' '.join(arguments)} failed: {message}")
    return completed.stdout


def make_writable_and_retry(
    function: Callable[[str], object], path: str, _error: BaseException
) -> None:
    """Windows refuses to delete read-only files, and git writes packs read-only."""
    os.chmod(path, stat.S_IWRITE)
    function(path)


def fetch_clone(url: str) -> Path:
    """A blob-less bare clone of the source with every branch and tag, up to date."""
    clone = find_cache_directory(url) / "clone.git"
    if not clone.is_dir():
        clone.parent.mkdir(parents=True, exist_ok=True)
        pending = Path(tempfile.mkdtemp(dir=clone.parent, prefix="clone-"))
        run_git("clone", "--quiet", "--bare", "--filter=blob:none", url, str(pending))
        try:
            pending.replace(clone)
        except OSError:
            # A parallel run (pre-commit runs hooks in parallel) cloned it first.
            shutil.rmtree(pending, onexc=make_writable_and_retry)
            if not clone.is_dir():
                raise
        return clone
    run_git(
        "fetch", "--quiet", "--prune", "--filter=blob:none", "origin",
        "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*",
        cwd=clone,
    )  # fmt: skip
    return clone


def resolve_ref(url: str, ref: str) -> str:
    clone = fetch_clone(url)
    return (
        run_git("rev-parse", "--verify", f"{ref}^{{commit}}", cwd=clone)
        .decode()
        .strip()
    )


def find_cached_commit(url: str, commit: str) -> Path | None:
    path = find_cache_directory(url) / commit
    return path if path.is_dir() else None


def fetch_commit(url: str, commit: str) -> Path:
    """Extract one commit into the cache, through a temporary folder and a rename."""
    if found := find_cached_commit(url, commit):
        return found
    clone = find_cache_directory(url) / "clone.git"
    try:
        run_git("cat-file", "-e", f"{commit}^{{commit}}", cwd=clone)
    except (ConfigError, OSError):
        clone = fetch_clone(url)
    archive = run_git("archive", "--format=tar", commit, cwd=clone)
    final = find_cache_directory(url) / commit
    pending = Path(tempfile.mkdtemp(dir=final.parent, prefix="commit-"))
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(pending, filter="data")
    try:
        pending.replace(final)
    except OSError:
        shutil.rmtree(pending)
        if not final.is_dir():
            raise
    return final


def find_locked_entry(name: str, source: PackSource, lock: Lock) -> LockEntry:
    entry = lock.sources.get(name)
    if entry is None:
        raise ConfigError(f"source {name!r} is not in the lock; {LOCK_COMMAND}")
    if (entry.git, entry.ref) != (source.git, source.ref):
        raise ConfigError(
            f"source {name!r} changed since it was locked "
            f"({entry.git}@{entry.ref}); {LOCK_COMMAND}"
        )
    return entry


def find_source_root(name: str, source: PackSource, lock: Lock, fetch: bool) -> Path:
    if source.path is not None:
        return source.path
    entry = find_locked_entry(name, source, lock)
    if fetch:
        return fetch_commit(entry.git, entry.commit)
    if found := find_cached_commit(entry.git, entry.commit):
        return found
    raise PacksNotCached(f"source {name!r} is not cached; {LOCK_COMMAND}")


def lock_sources(config: ResolvedConfig, update: set[str] | None = None) -> Lock:
    """Pin every git source, re-resolving the ones in `update` (None: none)."""
    previous = read_lock(config.lock_file)
    lock = Lock()
    for name, source in sorted(config.values.sources.items()):
        if source.git is None or source.ref is None:
            continue
        entry = previous.sources.get(name)
        unchanged = entry is not None and (entry.git, entry.ref) == (
            source.git,
            source.ref,
        )
        if entry is None or not unchanged or name in (update or set()):
            entry = LockEntry(
                git=source.git,
                ref=source.ref,
                commit=resolve_ref(source.git, source.ref),
            )
        fetch_commit(entry.git, entry.commit)
        lock.sources[name] = entry
    return lock
