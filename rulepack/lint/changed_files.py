import subprocess
from pathlib import Path


class ChangedFilesError(Exception):
    pass


def run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def read_git_lines(root: Path, *arguments: str) -> list[str]:
    completed = run_git(root, *arguments)
    if completed.returncode != 0:
        raise ChangedFilesError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return [line for line in completed.stdout.splitlines() if line]


def ref_exists(root: Path, ref: str) -> bool:
    completed = run_git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return completed.returncode == 0


def strip_remote_prefix(ref: str) -> str:
    """`origin/main` -> `main`; a ref without a remote prefix stays as it is."""
    return ref.split("/", 1)[1] if "/" in ref else ref


def resolve_base_ref(root: Path, explicit: str | None, default: str) -> str | None:
    if explicit is not None:
        if not ref_exists(root, explicit):
            raise ChangedFilesError(
                f"base ref '{explicit}' does not exist. Fetch it first "
                "(CI: actions/checkout with fetch-depth: 0)."
            )
        return explicit
    for candidate in (default, strip_remote_prefix(default)):
        if ref_exists(root, candidate):
            return candidate
    return None


def resolve_diff_base(root: Path, base_ref: str | None, explicit: bool) -> str:
    if base_ref is not None:
        merge_base = run_git(root, "merge-base", base_ref, "HEAD")
        if merge_base.returncode == 0:
            return merge_base.stdout.strip()
        if explicit:
            raise ChangedFilesError(
                f"no merge base between '{base_ref}' and HEAD (shallow clone?)."
            )
    return "HEAD" if ref_exists(root, "HEAD") else "--cached"


def list_changed_files(
    root: Path,
    *,
    base_ref: str | None = None,
    default_base_ref: str = "origin/main",
    staged: bool = False,
    extensions: list[str] | None = None,
) -> list[Path]:
    """Changed files that still exist, as absolute paths, sorted.

    Without `staged`: committed changes since the merge base with the base ref,
    uncommitted changes, and untracked files. If the default base has no merge
    base, compare against HEAD (or include staged files before the first commit).
    An explicit base must resolve. With `staged`: only the staged files.
    """
    if staged:
        names = read_git_lines(
            root, "diff", "--cached", "--name-only", "--diff-filter=ACMR"
        )
    else:
        resolved = resolve_base_ref(root, base_ref, default_base_ref)
        base = resolve_diff_base(root, resolved, explicit=base_ref is not None)
        names = read_git_lines(
            root, "diff", "--name-only", "--diff-filter=ACMR", base, "--"
        )
        names += read_git_lines(root, "ls-files", "--others", "--exclude-standard")
    paths = {root / name for name in names}
    return sorted(
        path
        for path in paths
        if path.is_file() and (extensions is None or path.suffix in extensions)
    )
