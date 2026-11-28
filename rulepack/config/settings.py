from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

Source = Literal["default", "file", "flag"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScanSettings(StrictModel):
    exclude: list[str] = []
    extensions: list[str] = [".py"]


class ChangedSettings(StrictModel):
    base_ref: str = "origin/main"


class HookSettings(StrictModel):
    enabled: bool = True
    timeout: float = Field(default=10.0, gt=0, allow_inf_nan=False)


class GitSource(StrictModel):
    """Packs from a git repo at a branch, tag or commit."""

    git: str
    ref: str


class PathSource(StrictModel):
    """Packs from a local folder."""

    path: Path


def classify_source(value: Any) -> str:
    """A table with `path` is a path source; any other is a git source."""
    if isinstance(value, dict):
        return "path" if "path" in value else "git"
    return "path" if isinstance(value, PathSource) else "git"


PackSource = Annotated[
    Annotated[GitSource, Tag("git")] | Annotated[PathSource, Tag("path")],
    Discriminator(classify_source),
]


class ProjectConfig(StrictModel):
    sources: dict[str, PackSource] = {}
    sgconfig: Path = Path("lint/sgconfig.yml")
    importlinter: Path = Path(".importlinter")
    scan: ScanSettings = ScanSettings()
    hooks: HookSettings = HookSettings()
    changed: ChangedSettings = ChangedSettings()


class ResolvedConfig(StrictModel):
    """The merged config. Every path value is absolute."""

    root: Path
    git_root: Path | None
    file: Path | None
    # rulepack.lock, next to the config file.
    lock_file: Path
    values: ProjectConfig
    sources: dict[str, Source]
