import tempfile
import tomllib
from pathlib import Path

import tomli_w
from pydantic import Field, ValidationError

from rulepack.config import ConfigError, StrictModel

LOCK_HEADER = "# Written by `rulepack packs lock`. Commit this file.\n\n"


class LockEntry(StrictModel):
    git: str
    ref: str
    commit: str


class Lock(StrictModel):
    sources: dict[str, LockEntry] = Field(default_factory=dict)


def read_lock(path: Path) -> Lock:
    if not path.is_file():
        return Lock()
    try:
        return Lock.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise ConfigError(f"{path}: {error}") from error


def render_lock(lock: Lock) -> str:
    sources = {name: lock.sources[name].model_dump() for name in sorted(lock.sources)}
    return LOCK_HEADER + tomli_w.dumps({"sources": sources})


def write_lock(path: Path, lock: Lock) -> None:
    """Write through a temporary file and a rename; an unchanged lock is not touched."""
    text = render_lock(lock)
    if path.is_file() and path.read_bytes() == text.encode("utf-8"):
        return
    # newline="\n": the same bytes on every OS, so a lock written on Windows
    # does not churn against one written elsewhere.
    with tempfile.NamedTemporaryFile(
        "w",
        dir=path.parent,
        delete=False,
        encoding="utf-8",
        newline="\n",
        suffix=".tmp",
    ) as pending:
        pending.write(text)
    Path(pending.name).replace(path)
