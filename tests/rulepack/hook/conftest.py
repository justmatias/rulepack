from pathlib import Path

import pytest


@pytest.fixture
def violating_target(lint_sandbox: Path, bare_except_source: str) -> Path:
    target = lint_sandbox / "target.py"
    target.write_text(bare_except_source, encoding="utf-8")
    return target


@pytest.fixture(params=["invalid/target.py", "target.txt"])
def unscanned_target(
    lint_sandbox: Path, bare_except_source: str, request: pytest.FixtureRequest
) -> Path:
    """A violating file that the sample config excludes or does not scan."""
    target = lint_sandbox / request.param
    target.write_text(bare_except_source, encoding="utf-8")
    return target


@pytest.fixture
def append_config(lint_sandbox: Path):
    def append(content: str) -> None:
        with (lint_sandbox / ".rulepack.toml").open("a", encoding="utf-8") as stream:
            stream.write("\n" + content)

    return append


@pytest.fixture(params=["  *** Add File: target.py", "*** Add File: target.py  "])
def padded_add_header(request: pytest.FixtureRequest) -> str:
    return request.param
