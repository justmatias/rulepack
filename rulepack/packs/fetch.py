import hashlib
import io
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
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


def move_into_place(pending: Path, final: Path) -> None:
    """Rename `pending` to `final`, or drop it when a parallel run got there first.

    pre-commit runs hooks in parallel, so two runs can fetch the same thing at once.
    """
    try:
        pending.replace(final)
    except OSError:
        shutil.rmtree(pending, onexc=retry_after_making_writable)
        if not final.is_dir():
            raise


def fetch_clone(url: str) -> Path:
    """A blob-less bare clone of the source with every branch and tag, up to date."""
    clone = locate_cache_directory(url) / "clone.git"
    if not clone.is_dir():
        clone.parent.mkdir(parents=True, exist_ok=True)
        pending = Path(tempfile.mkdtemp(dir=clone.parent, prefix="clone-"))
        run_git("clone", "--quiet", "--bare", "--filter=blob:none", url, str(pending))
        move_into_place(pending, clone)
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


def fetch_commit(url: str, commit: str) -> Path:
    """The commit's files in the cache, extracted through a temporary folder."""
    final = locate_cache_directory(url) / commit
    if final.is_dir():
        return final
    clone = final.parent / "clone.git"
    try:
        run_git("cat-file", "-e", f"{commit}^{{commit}}", cwd=clone)
    except (ConfigError, OSError):
        clone = fetch_clone(url)
    archive = run_git("archive", "--format=tar", commit, cwd=clone)
    pending = Path(tempfile.mkdtemp(dir=final.parent, prefix="commit-"))
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(pending, filter="data")
    move_into_place(pending, final)
    return final
