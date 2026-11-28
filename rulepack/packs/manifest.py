import tomllib
from pathlib import Path

from pydantic import Field, ValidationError

from rulepack.config import ConfigError, StrictModel

MANIFEST_FILE_NAME = "packs.toml"


class ManifestPack(StrictModel):
    checks: list[str]


class Manifest(StrictModel):
    checks_dir: Path = Path("lint/rules")
    tests_dir: Path = Path("lint/rule-tests")
    packs: dict[str, ManifestPack] = Field(default_factory=dict)


def resolve_inside(root: Path, relative: Path, what: str) -> Path:
    """`root / relative`, which must not leave `root`."""
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
