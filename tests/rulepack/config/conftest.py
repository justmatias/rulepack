from pathlib import Path

import pytest


@pytest.fixture
def _write_sgconfig_config(write_config) -> None:
    write_config('sgconfig = "checks/sgconfig.yml"\n')


@pytest.fixture(
    params=[
        'git = "https://example.invalid/team.git"\nref = "main"\npath = "team"\n',
        "",
        'git = "https://example.invalid/team.git"\n',
        'path = "team"\nref = "main"\n',
    ],
    ids=["git-and-path", "neither", "git-without-ref", "path-with-ref"],
)
def invalid_source(request: pytest.FixtureRequest) -> str:
    return f"[sources.team]\n{request.param}"


@pytest.fixture
def _change_to_git_repository(git_repository: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repository)
