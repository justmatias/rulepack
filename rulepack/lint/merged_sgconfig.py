import contextlib
import logging
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import yaml

from rulepack.config import ConfigError, PackOverrides, ResolvedConfig, StrictModel
from rulepack.packs.sources import Pack

logger = logging.getLogger(__name__)


class PackCheck(StrictModel):
    # `<source>/<pack>`, to name both packs when two define one id.
    pack: str
    document: dict[str, Any]


def read_local_sgconfig(config: ResolvedConfig) -> dict[str, Any]:
    """The repo's sgconfig with absolute paths, or an empty one when it has none.

    Only the default path may be missing: a repo that sets `sgconfig` expects it.
    """
    path = config.values.sgconfig
    if not path.is_file():
        if config.sources["sgconfig"] != "default":
            raise ConfigError(f"no ast-grep config at {path}")
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("ruleDirs", "utilDirs"):
        if key in data:
            data[key] = [str(path.parent / directory) for directory in data[key]]
    for entry in data.get("testConfigs") or []:
        entry["testDir"] = str(path.parent / entry["testDir"])
    for entry in (data.get("customLanguages") or {}).values():
        entry["libraryPath"] = str(path.parent / entry["libraryPath"])
    return data


def collect_local_check_ids(data: dict[str, Any]) -> set[str]:
    return {
        entry["id"]
        for directory in data.get("ruleDirs", [])
        for path in Path(directory).rglob("*.y*ml")
        for entry in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if entry and "id" in entry
    }


def collect_pack_checks(packs: list[Pack]) -> dict[str, PackCheck]:
    """Every pack check by id; one id in two packs is an error."""
    checks: dict[str, PackCheck] = {}
    for pack in packs:
        qualified = f"{pack.source}/{pack.name}"
        for path in pack.checks:
            for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
                if not document:
                    continue
                check_id = document.get("id") if isinstance(document, dict) else None
                if not isinstance(check_id, str) or not check_id:
                    raise ConfigError(
                        f"pack {qualified!r}: {path} has a rule with no id"
                    )
                if check_id in checks:
                    raise ConfigError(
                        f"check {check_id!r} is in pack {checks[check_id].pack!r} "
                        f"and in pack {qualified!r}; select only one of them"
                    )
                checks[check_id] = PackCheck(pack=qualified, document=document)
    return checks


def select_pack_check_ids(
    checks: dict[str, PackCheck], local_ids: set[str], overrides: PackOverrides
) -> set[str]:
    """The pack checks to run: not disabled, and not replaced by the repo's own."""
    if unknown := (set(overrides.disable) | overrides.severity.keys()) - checks.keys():
        raise ConfigError(
            f"pack_overrides: unknown checks: {', '.join(sorted(unknown))}"
        )
    for check_id in sorted(local_ids & checks.keys()):
        logger.info("lint: the repo's check %s replaces the pack check", check_id)
    return checks.keys() - local_ids - set(overrides.disable)


def write_pack_checks(
    directory: Path,
    checks: dict[str, PackCheck],
    selected: set[str],
    overrides: PackOverrides,
) -> None:
    directory.mkdir()
    for index, check_id in enumerate(sorted(selected)):
        document = dict(checks[check_id].document)
        if check_id in overrides.severity:
            document["severity"] = overrides.severity[check_id]
        (directory / f"{index}.yml").write_text(
            yaml.safe_dump(document), encoding="utf-8"
        )


def write_pack_tests(directory: Path, packs: list[Pack], selected: set[str]) -> None:
    directory.mkdir()
    tests = sorted({test for pack in packs for test in pack.tests})
    for index, path in enumerate(tests):
        cases = [
            case
            for case in yaml.safe_load_all(path.read_text(encoding="utf-8"))
            if case and case.get("id") in selected
        ]
        if cases:
            (directory / f"{index}.yml").write_text(
                yaml.safe_dump_all(cases), encoding="utf-8"
            )


@contextlib.contextmanager
def write_merged_sgconfig(
    config: ResolvedConfig, packs: list[Pack], *, include_tests: bool
) -> Generator[Path, None, None]:
    """A temporary sgconfig with the repo's checks and the packs' checks.

    With `include_tests`, the packs' rule tests too: a scan alone never reads them,
    so a broken test file in a pack cannot block it.
    """
    with tempfile.TemporaryDirectory(prefix="rulepack-packs-") as directory:
        root = Path(directory)
        data = read_local_sgconfig(config)
        checks = collect_pack_checks(packs)
        overrides = config.values.pack_overrides
        selected = select_pack_check_ids(
            checks, collect_local_check_ids(data), overrides
        )
        write_pack_checks(root / "rules", checks, selected, overrides)
        data["ruleDirs"] = [*data.get("ruleDirs", []), str(root / "rules")]
        if include_tests:
            write_pack_tests(root / "tests", packs, selected)
            data["testConfigs"] = [
                *(data.get("testConfigs") or []),
                {"testDir": str(root / "tests")},
            ]
        path = root / "sgconfig.yml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        yield path
