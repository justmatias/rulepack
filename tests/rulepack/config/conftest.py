from pathlib import Path

import pytest


@pytest.fixture
def _write_sgconfig_config(write_config) -> None:
    write_config('sgconfig = "checks/sgconfig.yml"\n')


@pytest.fixture
def _change_to_git_repository(git_repository: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repository)


@pytest.fixture(
    params=[
        'rule_dir = "rules"\n',
        '[scan]\nexcludes = ["generated/**"]\n',
        'rules_dir = "rules"\n',
    ],
    ids=["top-level", "nested", "removed-key"],
)
def _write_unknown_key_config(write_config, request: pytest.FixtureRequest) -> None:
    write_config(request.param)
