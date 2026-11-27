from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class ProjectConfig(StrictModel):
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
    values: ProjectConfig
    sources: dict[str, Source]
