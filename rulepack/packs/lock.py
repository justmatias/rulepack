import json
import re
import tempfile
import tomllib
from pathlib import Path

from pydantic import Field, ValidationError

from rulepack.config import ConfigError, StrictModel

BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


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


def format_toml_key(name: str) -> str:
    return name if BARE_KEY.fullmatch(name) else json.dumps(name)


def render_lock(lock: Lock) -> str:
    lines = ["# Written by `rulepack packs lock`. Commit this file.", ""]
    for name in sorted(lock.sources):
        entry = lock.sources[name]
        lines += [
            f"[sources.{format_toml_key(name)}]",
            f"git = {json.dumps(entry.git)}",
            f"ref = {json.dumps(entry.ref)}",
            f"commit = {json.dumps(entry.commit)}",
            "",
        ]
    return "\n".join(lines).rstrip("\n") + "\n"


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
