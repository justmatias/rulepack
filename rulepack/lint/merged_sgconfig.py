import contextlib
import logging
import re
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import yaml

from rulepack.config import ConfigError, PackOverrides, ResolvedConfig, StrictModel
from rulepack.packs.manifest import resolve_inside
from rulepack.packs.sources import Pack

logger = logging.getLogger(__name__)


class PackCheck(StrictModel):
    # `<source>/<pack>`, to name both packs when two define one id.
    pack: str
    document: dict[str, Any]
    tests_dir: Path


# ast-grep reads YAML 1.2, where plain `on` and dates are strings.
AST_GREP_RESOLVERS = {
    initial: [
        (tag, pattern)
        for tag, pattern in resolvers
        if tag not in {"tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp"}
    ]
    for initial, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
for initial in "tTfF":
    AST_GREP_RESOLVERS[initial].append((
        "tag:yaml.org,2002:bool",
        re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    ))


@contextlib.contextmanager
def open_ast_grep_yaml(path: Path) -> Generator[yaml.SafeLoader, None, None]:
    loader = yaml.SafeLoader(path.read_text(encoding="utf-8"))
    loader.yaml_implicit_resolvers = AST_GREP_RESOLVERS
    try:
        yield loader
    finally:
        loader.dispose()


def read_rule_documents(path: Path) -> Generator[Any, None, None]:
    with open_ast_grep_yaml(path) as loader:
        while loader.check_node():
            node = loader.get_node()
            if isinstance(node, yaml.MappingNode):
                for key, value in node.value:
                    if (
                        isinstance(key, yaml.ScalarNode)
                        and key.value == "id"
                        and isinstance(value, yaml.ScalarNode)
                        and value.tag != "tag:yaml.org,2002:null"
                    ):
                        value.tag = "tag:yaml.org,2002:str"
            yield loader.construct_document(node)


def list_rule_yaml(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*")
        if path.suffix in {".yml", ".yaml"}
        and not any(part.startswith(".") for part in path.relative_to(directory).parts)
        and path.is_file()
    )


def read_local_sgconfig(path: Path | None) -> dict[str, Any]:
    """The repo's sgconfig with absolute paths, or an empty one when it has none."""
    if path is None:
        return {}
    with open_ast_grep_yaml(path) as loader:
        data = loader.get_single_data()
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: the ast-grep config must be a mapping")
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
        for path in list_rule_yaml(Path(directory))
        for entry in read_rule_documents(path)
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def collect_pack_checks(packs: list[Pack]) -> dict[str, PackCheck]:
    """Every pack check by id; one id in two packs is an error."""
    checks: dict[str, PackCheck] = {}
    for pack in packs:
        qualified = f"{pack.source}/{pack.name}"
        for path in pack.checks:
            for document in read_rule_documents(path):
                if document is None:
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
                checks[check_id] = PackCheck(
                    pack=qualified, document=document, tests_dir=pack.tests_dir
                )
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


def write_pack_tests(
    directory: Path, checks: dict[str, PackCheck], selected: set[str]
) -> None:
    directory.mkdir()
    check_ids_by_directory: dict[Path, set[str]] = {}
    for check_id in selected:
        check_ids_by_directory.setdefault(checks[check_id].tests_dir, set()).add(
            check_id
        )
    index = 0
    for tests_dir, check_ids in sorted(check_ids_by_directory.items()):
        for path in list_rule_yaml(tests_dir):
            resolved = resolve_inside(
                tests_dir, path.relative_to(tests_dir), "rule test"
            )
            cases = read_pack_test_cases(resolved, check_ids)
            if cases:
                (directory / f"{index}.yml").write_text(
                    yaml.safe_dump_all(cases), encoding="utf-8"
                )
                index += 1


def read_pack_test_cases(path: Path, check_ids: set[str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for document in read_rule_documents(path):
        if document is None:
            continue
        if not isinstance(document, dict):
            raise ConfigError(f"{path}: every rule test must be a mapping")
        check_id = document.get("id")
        if not isinstance(check_id, str):
            raise ConfigError(f"{path}: every rule test needs a string id")
        if check_id in check_ids:
            cases.append(document)
    return cases


@contextlib.contextmanager
def write_merged_sgconfig(
    config: ResolvedConfig,
    packs: list[Pack],
    *,
    local_sgconfig: Path | None,
    include_tests: bool,
) -> Generator[Path, None, None]:
    """A temporary sgconfig with the repo's checks and the packs' checks.

    With `include_tests`, the packs' rule tests too: a scan alone never reads them,
    so a broken test file in a pack cannot block it.
    """
    with tempfile.TemporaryDirectory(prefix="rulepack-packs-") as directory:
        root = Path(directory)
        data = read_local_sgconfig(local_sgconfig)
        checks = collect_pack_checks(packs)
        overrides = config.values.pack_overrides
        selected = select_pack_check_ids(
            checks, collect_local_check_ids(data), overrides
        )
        write_pack_checks(root / "rules", checks, selected, overrides)
        data["ruleDirs"] = [*data.get("ruleDirs", []), str(root / "rules")]
        if include_tests:
            write_pack_tests(root / "tests", checks, selected)
            data["testConfigs"] = [
                *(data.get("testConfigs") or []),
                {"testDir": str(root / "tests")},
            ]
        path = root / "sgconfig.yml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        yield path
