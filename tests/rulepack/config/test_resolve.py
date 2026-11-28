from pathlib import Path

import pytest

from rulepack.config import ConfigError, resolve_config


def test_config_uses_defaults_when_file_is_missing(git_repository: Path):
    config = resolve_config(start=git_repository)

    assert config.file is None
    assert config.root == git_repository
    assert config.values.sgconfig == git_repository / "lint/sgconfig.yml"
    assert set(config.sources.values()) == {"default"}


def test_config_reads_rulepack_toml_when_it_exists(git_repository: Path, write_config):
    write_config(
        'sgconfig = "checks/sgconfig.yml"\n[scan]\nexclude = ["generated/**"]\n'
    )

    config = resolve_config(start=git_repository)

    assert config.values.sgconfig == git_repository / "checks/sgconfig.yml"
    assert config.values.scan.exclude == ["generated/**"]
    assert config.sources["sgconfig"] == "file"
    assert config.sources["scan.exclude"] == "file"
    assert config.sources["scan.extensions"] == "default"


def test_pyproject_table_is_ignored_when_no_rulepack_toml(
    git_repository: Path, write_config
):
    write_config(
        '[tool.rulepack]\nsgconfig = "checks/sgconfig.yml"\n', name="pyproject.toml"
    )

    assert resolve_config(start=git_repository).file is None


@pytest.mark.parametrize(
    "content",
    [
        'rule_dir = "rules"\n',
        '[scan]\nexcludes = ["generated/**"]\n',
        'rules_dir = "rules"\n',
    ],
    ids=["top-level", "nested", "removed-key"],
)
def test_config_fails_when_key_is_unknown(
    git_repository: Path, write_config, content: str
):
    write_config(content)

    with pytest.raises(ConfigError, match="Extra inputs are not permitted"):
        resolve_config(start=git_repository)


@pytest.mark.usefixtures("_write_sgconfig_config", "_change_to_git_repository")
def test_flag_overrides_file_when_both_set_a_key(git_repository: Path):
    config = resolve_config({
        "sgconfig": Path("other/sgconfig.yml"),
        "importlinter": None,
    })

    assert config.values.sgconfig == git_repository / "other/sgconfig.yml"
    assert config.sources["sgconfig"] == "flag"
    assert config.sources["importlinter"] == "default"


@pytest.mark.usefixtures("_write_sgconfig_config")
def test_config_is_found_when_started_from_a_subfolder(git_repository: Path):
    subfolder = git_repository / "package" / "module"
    subfolder.mkdir(parents=True)

    config = resolve_config(start=subfolder)

    assert config.file == git_repository / ".rulepack.toml"
    assert config.values.sgconfig == git_repository / "checks/sgconfig.yml"


def test_config_is_not_found_when_it_is_above_the_git_root(git_repository: Path):
    (git_repository.parent / ".rulepack.toml").write_text('sgconfig = "outside.yml"\n')

    config = resolve_config(start=git_repository)

    assert config.file is None
    assert config.values.sgconfig == git_repository / "lint/sgconfig.yml"


def test_config_resolves_a_path_source_against_the_config_when_started_below_it(
    git_repository: Path, write_config
):
    write_config('[sources.team]\npath = "packs/team"\n')

    config = resolve_config(start=git_repository / "packs")

    assert config.values.sources["team"].path == git_repository / "packs/team"
    assert config.lock_file == git_repository / "rulepack.lock"


def test_config_fails_when_a_source_is_not_one_git_ref_or_one_path(
    git_repository: Path, write_config, invalid_source: str
):
    write_config(invalid_source)

    with pytest.raises(ConfigError, match=r"sources\.team"):
        resolve_config(start=git_repository)
