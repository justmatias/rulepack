from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Source = Literal["default", "host", "file", "flag"]


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


class PackSource(StrictModel):
    """Where packs come from: a git repo at a ref, or a local folder."""

    git: str | None = None
    ref: str | None = None
    path: Path | None = None

    @model_validator(mode="after")
    def check_kind(self) -> "PackSource":
        if (self.git is None) == (self.path is None):
            raise ValueError("a source has exactly one of 'git' or 'path'")
        if (self.git is None) != (self.ref is None):
            raise ValueError("a git source needs a 'ref', and a path source has none")
        return self


class PackOverrides(StrictModel):
    disable: list[str] = []
    severity: dict[str, Literal["error", "warning", "info", "hint"]] = {}


class HostConfig(StrictModel):
    """This machine's default packs, for repos without a config file."""

    packs: list[str] = []
    sources: dict[str, PackSource] = {}


class ProjectConfig(StrictModel):
    # `<source>/<pack>` names, from `sources`.
    packs: list[str] = []
    sources: dict[str, PackSource] = {}
    pack_overrides: PackOverrides = PackOverrides()
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
    # rulepack.lock next to the file that declares the sources.
    lock_file: Path
    values: ProjectConfig
    sources: dict[str, Source]
