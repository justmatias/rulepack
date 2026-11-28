import pytest

from tests.rulepack.helpers import run_git

# The hook keeps its stop marker in the temp directory, so every test isolates it.
pytestmark = pytest.mark.usefixtures("_isolate_temp_directory")

QUIET = (0, "", "")


@pytest.mark.usefixtures("violating_target")
def test_post_edit_reports_finding_when_file_violates_rule(lint_sandbox, run_hook):
    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": "target.py"})

    assert result.returncode == 2
    assert "target.py:3: no-bare-except" in result.stderr


def test_post_edit_checks_only_edited_file_when_other_file_has_exception(
    lint_sandbox, run_hook, bare_except_source
):
    (lint_sandbox / "other.py").write_text(
        "# ast-grep-ignore: no-bare-except\n" + bare_except_source, encoding="utf-8"
    )
    (lint_sandbox / "target.py").write_text("value = 1\n", encoding="utf-8")

    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": "target.py"})

    assert (result.returncode, result.stdout, result.stderr) == QUIET


def test_post_edit_is_silent_when_repository_has_no_config(
    lint_sandbox, run_hook, violating_target
):
    (lint_sandbox / ".rulepack.toml").unlink()

    result = run_hook(
        lint_sandbox, "post-edit", tool_input={"file_path": str(violating_target)}
    )

    assert (result.returncode, result.stdout, result.stderr) == QUIET


def test_post_edit_is_silent_when_file_is_not_scanned(
    lint_sandbox, run_hook, unscanned_target
):
    result = run_hook(
        lint_sandbox, "post-edit", tool_input={"file_path": str(unscanned_target)}
    )

    assert (result.returncode, result.stdout, result.stderr) == QUIET


def test_post_edit_is_silent_when_hooks_are_disabled(
    lint_sandbox, run_hook, violating_target, append_config
):
    append_config("[hooks]\nenabled = false\n")

    result = run_hook(
        lint_sandbox, "post-edit", tool_input={"file_path": str(violating_target)}
    )

    assert (result.returncode, result.stdout, result.stderr) == QUIET


@pytest.mark.usefixtures("violating_target")
def test_post_edit_warns_when_time_budget_expires(
    lint_sandbox, run_hook, append_config
):
    append_config("[hooks]\ntimeout = 0.000001\n")

    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": "target.py"})

    assert result.returncode == 0
    assert "timed out" in result.stderr


@pytest.mark.usefixtures("violating_target")
def test_post_edit_warns_when_payload_is_malformed(lint_sandbox, run_hook):
    result = run_hook(lint_sandbox, "post-edit", tool_input="target.py")

    assert (result.returncode, result.stdout) == (0, "")
    assert "validation error" in result.stderr


@pytest.mark.usefixtures("violating_target")
def test_stop_reports_finding_when_changed_file_violates_rule(lint_sandbox, run_hook):
    result = run_hook(lint_sandbox, "stop", session_id="one")

    assert result.returncode == 2
    assert "no-bare-except" in result.stderr


@pytest.mark.usefixtures("violating_target")
def test_stop_is_silent_when_session_already_reported_findings(lint_sandbox, run_hook):
    run_hook(lint_sandbox, "stop", session_id="one")

    result = run_hook(lint_sandbox, "stop", session_id="one")

    assert (result.returncode, result.stdout, result.stderr) == QUIET


@pytest.mark.usefixtures("violating_target")
def test_stop_is_silent_when_repository_has_no_config(lint_sandbox, run_hook):
    (lint_sandbox / ".rulepack.toml").unlink()

    result = run_hook(lint_sandbox, "stop", session_id="one")

    assert (result.returncode, result.stdout, result.stderr) == QUIET


def test_post_edit_reports_finding_when_cursor_supplies_workspace_root(
    lint_sandbox, run_hook, violating_target
):
    result = run_hook(
        lint_sandbox,
        "post-edit",
        cwd=None,
        workspace_roots=[str(lint_sandbox)],
        file_path=str(violating_target),
    )

    assert result.returncode == 2
    assert "no-bare-except" in result.stderr


@pytest.mark.usefixtures("violating_target")
def test_post_edit_uses_installed_cli_when_repo_has_matching_module(
    lint_sandbox, run_hook
):
    (lint_sandbox / "rulepack.py").write_text("value = 1\n", encoding="utf-8")

    result = run_hook(lint_sandbox, "post-edit", tool_input={"file_path": "target.py"})

    assert result.returncode == 2
    assert "no-bare-except" in result.stderr


def test_post_edit_is_silent_when_nested_repo_has_no_config(
    lint_sandbox, run_hook, bare_except_source
):
    nested = lint_sandbox / "nested"
    nested.mkdir()
    run_git(nested, "init")
    (nested / "target.py").write_text(bare_except_source, encoding="utf-8")

    result = run_hook(
        lint_sandbox, "post-edit", tool_input={"file_path": "nested/target.py"}
    )

    assert (result.returncode, result.stdout, result.stderr) == QUIET


def test_stop_scans_tracked_edit_when_default_base_is_missing(
    lint_sandbox, run_hook, commit, bare_except_source
):
    target = lint_sandbox / "target.py"
    target.write_text("value = 1\n", encoding="utf-8")
    commit(lint_sandbox)
    run_git(lint_sandbox, "branch", "-m", "other")
    (lint_sandbox / "HEAD").touch()
    target.write_text(bare_except_source, encoding="utf-8")

    result = run_hook(lint_sandbox, "stop", session_id="one")

    assert result.returncode == 2
    assert "no-bare-except" in result.stderr


def test_post_edit_reports_all_findings_when_codex_applies_a_patch(
    lint_sandbox, run_hook, bare_except_source
):
    for filename in ("first.py", "renamed file.py", "context.py"):
        (lint_sandbox / filename).write_text(bare_except_source, encoding="utf-8")

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


@pytest.mark.usefixtures("violating_target")
def test_post_edit_is_silent_when_codex_patch_only_deletes_files(
    lint_sandbox, run_hook
):
    result = run_hook(
        lint_sandbox,
        "post-edit",
        tool_name="apply_patch",
        tool_input={
            "command": "*** Begin Patch\n*** Delete File: target.py\n*** End Patch\n"
        },
    )

    assert (result.returncode, result.stdout, result.stderr) == QUIET


@pytest.mark.usefixtures("violating_target")
def test_post_edit_reports_finding_when_codex_patch_header_has_padding(
    lint_sandbox, run_hook, padded_add_header, bare_except_source
):
    added_lines = "".join(f"+{line}\n" for line in bare_except_source.splitlines())
    patch = f"*** Begin Patch\n{padded_add_header}\n{added_lines}*** End Patch\n"

    result = run_hook(
        lint_sandbox,
        "post-edit",
        tool_name="apply_patch",
        tool_input={"command": patch},
    )

    assert result.returncode == 2
    assert "target.py:3: no-bare-except" in result.stderr
