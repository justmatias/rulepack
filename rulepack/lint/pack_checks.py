import logging
from pathlib import Path

import yaml

from rulepack.config import ConfigError, ResolvedConfig
from rulepack.packs.sources import Pack

logger = logging.getLogger(__name__)


def read_local_sgconfig(path: Path | None) -> dict:
    """The repo's sgconfig with absolute paths, or nothing when it has none."""
    if path is None:
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


def collect_local_check_ids(data: dict) -> set[str]:
    return {
        entry["id"]
        for directory in data.get("ruleDirs", [])
        for path in Path(directory).rglob("*.y*ml")
        for entry in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if entry and "id" in entry
    }


def index_pack_checks(packs: list[Pack]) -> dict[str, tuple[str, dict]]:
    """Every pack check by id, with the pack it comes from."""
    checks: dict[str, tuple[str, dict]] = {}
    for pack in packs:
        qualified = f"{pack.source}/{pack.name}"
        for path in pack.checks:
            for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
                if not document:
                    continue
                check_id = document["id"]
                if check_id in checks:
                    raise ConfigError(
                        f"check {check_id!r} is in pack {checks[check_id][0]!r} "
                        f"and in pack {qualified!r}; select only one of them"
                    )
                checks[check_id] = (qualified, document)
    return checks


def write_pack_tests(directory: Path, packs: list[Pack], selected: set[str]) -> None:
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


def select_pack_checks(
    config: ResolvedConfig, checks: dict[str, tuple[str, dict]], local_ids: set[str]
) -> set[str]:
    """The pack checks to run: not disabled, and not replaced by a repo check."""
    overrides = config.values.pack_overrides
    if unknown := (set(overrides.disable) | overrides.severity.keys()) - checks.keys():
        raise ConfigError(
            f"pack_overrides: unknown checks: {', '.join(sorted(unknown))}"
        )
    for check_id in sorted(local_ids & checks.keys()):
        logger.info("lint: the repo's check %s replaces the pack check", check_id)
    return checks.keys() - local_ids - set(overrides.disable)


def write_merged_sgconfig(
    directory: Path,
    config: ResolvedConfig,
    packs: list[Pack],
    local_sgconfig: Path | None,
) -> Path:
    """An sgconfig in `directory` that adds the packs' checks and tests to the repo's."""
    data = read_local_sgconfig(local_sgconfig)
    checks = index_pack_checks(packs)
    selected = select_pack_checks(config, checks, collect_local_check_ids(data))
    severity = config.values.pack_overrides.severity
    rules_dir = directory / "rules"
    tests_dir = directory / "tests"
    rules_dir.mkdir()
    tests_dir.mkdir()
    for index, check_id in enumerate(sorted(selected)):
        document = checks[check_id][1]
        if check_id in severity:
            document["severity"] = severity[check_id]
        (rules_dir / f"{index}.yml").write_text(
            yaml.safe_dump(document), encoding="utf-8"
        )
    write_pack_tests(tests_dir, packs, selected)
    data.setdefault("ruleDirs", []).append(str(rules_dir))
    data["testConfigs"] = [
        *(data.get("testConfigs") or []),
        {"testDir": str(tests_dir)},
    ]
    path = directory / "sgconfig.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path
