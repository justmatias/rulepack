import hashlib
import io
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from rulepack.config import ConfigError


def locate_cache_directory(url: str) -> Path:
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


def retry_after_making_writable(
    function: Callable[[str], object], path: str, _error: BaseException
) -> None:
    """Windows refuses to delete read-only files, and git writes packs read-only."""
    os.chmod(path, stat.S_IWRITE)
    function(path)


@contextmanager
def stage_directory(parent: Path, prefix: str) -> Generator[Path, None, None]:
    pending = Path(tempfile.mkdtemp(dir=parent, prefix=prefix))
    try:
        yield pending
    finally:
        if pending.exists():
            shutil.rmtree(pending, onexc=retry_after_making_writable)


def move_into_place(pending: Path, final: Path) -> None:
    """Publish `pending` unless a parallel run got there first.

    pre-commit runs hooks in parallel, so two runs can fetch the same thing at once.
    """
    try:
        pending.replace(final)
    except OSError:
        if not final.is_dir():
            raise


def fetch_clone(url: str) -> Path:
    """A blob-less bare clone of the source with every branch and tag, up to date."""
    clone = locate_cache_directory(url) / "clone.git"
    if not clone.is_dir():
        clone.parent.mkdir(parents=True, exist_ok=True)
        with stage_directory(clone.parent, "clone-") as pending:
            run_git(
                "clone", "--quiet", "--bare", "--filter=blob:none", url, str(pending)
            )
            move_into_place(pending, clone)
        return clone
    run_git(
        "fetch", "--quiet", "--prune", "--filter=blob:none", "origin",
        "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*",
        cwd=clone,
    )  # fmt: skip
    return clone


def read_commit_id(clone: Path, ref: str) -> str:
    return (
        run_git("rev-parse", "--verify", f"{ref}^{{commit}}", cwd=clone)
        .decode()
        .strip()
    )


def resolve_ref(url: str, ref: str) -> str:
    return read_commit_id(fetch_clone(url), ref)


def fetch_commit(url: str, commit: str) -> Path:
    """The commit's files in the cache, extracted through a temporary folder."""
    final = locate_cache_directory(url) / commit
    if final.is_dir():
        return final
    clone = final.parent / "clone.git"
    try:
        resolved = read_commit_id(clone, commit)
    except (ConfigError, OSError):
        clone = fetch_clone(url)
        resolved = read_commit_id(clone, commit)
    if resolved != commit:
        raise ConfigError(f"locked object {commit} does not name its own commit")
    archive = run_git("archive", "--format=tar", commit, cwd=clone)
    with stage_directory(final.parent, "commit-") as pending:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(pending, filter="data")
        move_into_place(pending, final)
    return final
