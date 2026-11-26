import pytest

from rulepack.lint.changed_files import ChangedFilesError, changed_files
from tests.rulepack.lint.helpers import git, names


def test_lists_committed_uncommitted_and_untracked_files_when_not_staged(
    feature_repository, commit
):
    (feature_repository / "a.py").write_text("x = 2\n", encoding="utf-8")
    commit(feature_repository)
    (feature_repository / "b.py").write_text("x = 3\n", encoding="utf-8")
    (feature_repository / "new.py").write_text("y = 1\n", encoding="utf-8")

    changed = changed_files(feature_repository, default_base_ref="main")

    assert names(changed, feature_repository) == ["a.py", "b.py", "new.py"]


def test_leaves_out_files_when_they_were_deleted(feature_repository, commit):
    (feature_repository / "b.py").unlink()
    commit(feature_repository)

    assert changed_files(feature_repository, default_base_ref="main") == []


def test_lists_new_name_when_file_was_renamed(feature_repository, commit):
    git(feature_repository, "mv", "a.py", "renamed.py")
    commit(feature_repository)

    changed = changed_files(feature_repository, default_base_ref="main")

    assert names(changed, feature_repository) == ["renamed.py"]


def test_lists_only_staged_files_when_staged_is_set(feature_repository):
    (feature_repository / "a.py").write_text("x = 2\n", encoding="utf-8")
    (feature_repository / "b.py").write_text("x = 3\n", encoding="utf-8")
    git(feature_repository, "add", "a.py")

    changed = changed_files(feature_repository, staged=True)

    assert names(changed, feature_repository) == ["a.py"]


def test_fails_when_explicit_base_ref_is_missing(feature_repository):
    with pytest.raises(ChangedFilesError, match="does not exist"):
        changed_files(feature_repository, base_ref="origin/missing")


def test_falls_back_to_local_branch_when_default_base_ref_is_missing(
    feature_repository, commit
):
    (feature_repository / "a.py").write_text("x = 2\n", encoding="utf-8")
    commit(feature_repository)

    changed = changed_files(feature_repository, default_base_ref="origin/main")

    assert names(changed, feature_repository) == ["a.py"]


def test_filters_files_when_extensions_are_given(feature_repository, commit):
    (feature_repository / "a.py").write_text("x = 2\n", encoding="utf-8")
    (feature_repository / "notes.txt").write_text("changed\n", encoding="utf-8")
    commit(feature_repository)

    python_only = changed_files(
        feature_repository, default_base_ref="main", extensions=[".py"]
    )
    text_only = changed_files(
        feature_repository, default_base_ref="main", extensions=[".txt"]
    )

    assert names(python_only, feature_repository) == ["a.py"]
    assert names(text_only, feature_repository) == ["notes.txt"]
