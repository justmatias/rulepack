import pytest

from tests.rulepack.helpers import run_git

BARE_EXCEPT = "try:\n    value = 1\nexcept:\n    raise\n"


def test_post_edit_reports_finding_when_file_violates_rule(lint_sandbox, run_hook):
    target = lint_sandbox / "target.py"
    target.write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": "target.py"})

    assert result.returncode == 2
    assert "target.py:3: no-bare-except" in result.stderr


def test_post_edit_checks_only_edited_file_when_other_file_has_exception(
    lint_sandbox, run_hook
):
    (lint_sandbox / "other.py").write_text(
        "# ast-grep-ignore: no-bare-except\n" + BARE_EXCEPT, encoding="utf-8"
    )
    (lint_sandbox / "target.py").write_text("value = 1\n", encoding="utf-8")

    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": "target.py"})

    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


@pytest.mark.parametrize(
    "selection", ["unconfigured", "excluded", "extension", "disabled"]
)
def test_post_edit_is_silent_when_file_is_out_of_scope(
    lint_sandbox, run_hook, selection
):
    config = lint_sandbox / ".rulepack.toml"
    target = lint_sandbox / "target.py"
    if selection == "unconfigured":
        config.unlink()
    elif selection == "excluded":
        target = lint_sandbox / "invalid" / "target.py"
    elif selection == "extension":
        target = target.with_suffix(".txt")
    else:
        with config.open("a", encoding="utf-8") as stream:
            stream.write("\n[hooks]\nenabled = false\n")
    target.write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": str(target)})

    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_post_edit_warns_when_time_budget_expires(lint_sandbox, run_hook):
    with (lint_sandbox / ".rulepack.toml").open("a", encoding="utf-8") as stream:
        stream.write("\n[hooks]\ntimeout = 0.000001\n")
    (lint_sandbox / "target.py").write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": "target.py"})

    assert result.returncode == 0
    assert "timed out" in result.stderr


def test_stop_reports_once_when_findings_repeat(lint_sandbox, run_hook):
    (lint_sandbox / "target.py").write_text(BARE_EXCEPT, encoding="utf-8")

    first = run_hook(lint_sandbox, "stop", session_id="one")
    second = run_hook(lint_sandbox, "stop", session_id="one")

    assert first.returncode == 2
    assert "no-bare-except" in first.stderr
    assert (second.returncode, second.stdout, second.stderr) == (0, "", "")


def test_post_edit_reports_finding_when_cursor_supplies_workspace_root(
    lint_sandbox, run_hook
):
    target = lint_sandbox / "target.py"
    target.write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(
        lint_sandbox,
        "post-edit",
        cwd=None,
        workspace_roots=[str(lint_sandbox)],
        file_path=str(target),
    )

    assert result.returncode == 2
    assert "no-bare-except" in result.stderr


def test_post_edit_uses_installed_cli_when_repo_has_matching_module(
    lint_sandbox, run_hook
):
    (lint_sandbox / "rulepack.py").write_text("value = 1\n", encoding="utf-8")
    (lint_sandbox / "target.py").write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": "target.py"})

    assert result.returncode == 2
    assert "no-bare-except" in result.stderr


def test_post_edit_is_silent_when_nested_repo_has_no_config(lint_sandbox, run_hook):
    nested = lint_sandbox / "nested"
    nested.mkdir()
    run_git(nested, "init")
    (nested / "target.py").write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(
        lint_sandbox, "post-edit", tool_input={"file_path": "nested/target.py"}
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_stop_scans_tracked_edit_when_default_base_is_missing(
    lint_sandbox, run_hook, commit
):
    target = lint_sandbox / "target.py"
    target.write_text("value = 1\n", encoding="utf-8")
    commit(lint_sandbox)
    run_git(lint_sandbox, "branch", "-m", "other")
    (lint_sandbox / "HEAD").touch()
    target.write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(lint_sandbox, "stop", session_id="one")

    assert result.returncode == 2
    assert "no-bare-except" in result.stderr


def test_post_edit_reports_all_findings_when_codex_applies_a_patch(
    lint_sandbox, run_hook
):
    for filename in ("first.py", "renamed file.py", "context.py"):
        (lint_sandbox / filename).write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(
        lint_sandbox,
        "post-edit",
        tool_name="apply_patch",
        tool_input={
            "command": (
                "*** Begin Patch\n"
                "*** Add File: first.py\n"
                "+try:\n"
                "+    value = 1\n"
                "+except:\n"
                "+    raise\n"
                "*** Update File: old.py\n"
                "*** Move to: renamed file.py\n"
                "@@\n"
                " *** Add File: context.py\n"
                "-except ValueError:\n"
                "+except:\n"
                "*** End Patch\n"
            )
        },
    )

    assert result.returncode == 2
    assert "first.py:3: no-bare-except" in result.stderr
    assert "renamed file.py:3: no-bare-except" in result.stderr
    assert "context.py" not in result.stderr


def test_post_edit_is_silent_when_codex_patch_only_deletes_files(
    lint_sandbox, run_hook
):
    (lint_sandbox / "target.py").write_text(BARE_EXCEPT, encoding="utf-8")

    result = run_hook(
        lint_sandbox,
        "post-edit",
        tool_name="apply_patch",
        tool_input={
            "command": "*** Begin Patch\n*** Delete File: target.py\n*** End Patch\n"
        },
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


@pytest.mark.parametrize(
    "header", ["  *** Add File: target.py", "*** Add File: target.py  "]
)
def test_post_edit_reports_finding_when_codex_patch_header_has_padding(
    lint_sandbox, run_hook, header
):
    (lint_sandbox / "target.py").write_text(BARE_EXCEPT, encoding="utf-8")
    added_lines = "".join(f"+{line}\n" for line in BARE_EXCEPT.splitlines())
    patch = f"*** Begin Patch\n{header}\n{added_lines}*** End Patch\n"

    result = run_hook(
        lint_sandbox,
        "post-edit",
        tool_name="apply_patch",
        tool_input={"command": patch},
    )

    assert result.returncode == 2
    assert "target.py:3: no-bare-except" in result.stderr
