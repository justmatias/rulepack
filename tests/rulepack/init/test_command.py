import yaml

from tests.rulepack.init.helpers import read_tree

USER_PRE_COMMIT = (
    "# my hooks\n"
    "repos:\n"
    "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
    "    rev: v6.0.0\n"
    "    hooks:\n"
    "      - id: check-yaml\n"
    "\n"
    "default_stages: [pre-commit]\n"
)


def test_init_writes_only_a_config_that_passes_lint_when_checks_dir_is_not_given(
    run_init, git_repository
):
    completed = run_init("--yes")

    assert completed.returncode == 0, completed.stderr
    assert list(read_tree(git_repository)) == [".rulepack.toml"]
    assert "sgconfig" not in (git_repository / ".rulepack.toml").read_text()


def test_init_creates_local_checks_that_pass_lint_when_checks_dir_is_given(
    run_init, git_repository
):
    completed = run_init("--yes", "--checks-dir", "lint")

    assert completed.returncode == 0, completed.stderr
    assert sorted(read_tree(git_repository)) == [
        ".rulepack.toml",
        "lint/rule-tests/.gitkeep",
        "lint/rules/.gitkeep",
        "lint/sgconfig.yml",
    ]
    assert "lint: scan OK" in completed.stderr


def test_init_writes_checks_folder_to_config_when_it_is_given(run_init, git_repository):
    run_init("--yes", "--checks-dir", "checks")

    config = (git_repository / ".rulepack.toml").read_text(encoding="utf-8")
    assert 'sgconfig = "checks/sgconfig.yml"' in config
    assert (git_repository / "checks" / "sgconfig.yml").is_file()


def test_init_changes_nothing_when_run_twice(run_init, git_repository):
    run_init("--yes", "--pre-commit", "--ci", "github", "--makefile")
    before = read_tree(git_repository)

    completed = run_init("--yes", "--pre-commit", "--ci", "github", "--makefile")

    assert read_tree(git_repository) == before
    assert "nothing to write" in completed.stderr


def test_init_appends_hooks_when_pre_commit_config_exists(run_init, git_repository):
    (git_repository / ".pre-commit-config.yaml").write_text(USER_PRE_COMMIT)

    run_init("--yes", "--pre-commit")

    text = (git_repository / ".pre-commit-config.yaml").read_text()
    config = yaml.safe_load(text)
    assert [repo["repo"] for repo in config["repos"]] == [
        "https://github.com/pre-commit/pre-commit-hooks",
        "https://github.com/justmatias/rulepack",
    ]
    assert config["repos"][1]["rev"].startswith("v")
    assert config["default_stages"] == ["pre-commit"]
    assert text.startswith(USER_PRE_COMMIT.split("\n\n", maxsplit=1)[0])


def test_init_creates_pre_commit_config_when_it_is_missing(run_init, git_repository):
    run_init("--yes", "--pre-commit")

    config = yaml.safe_load((git_repository / ".pre-commit-config.yaml").read_text())
    assert config["repos"][0]["hooks"][0]["id"] == "rulepack-lint"


def test_init_skips_makefile_target_when_it_exists(run_init, git_repository):
    (git_repository / "Makefile").write_text("lint-rules:\n\techo mine\n")

    run_init("--yes", "--makefile")

    makefile = (git_repository / "Makefile").read_text()
    assert makefile.startswith("lint-rules:\n\techo mine\n")
    assert makefile.count("lint-rules:") == 1
    assert "lint-rules-changed:\n\trulepack lint --changed" in makefile


def test_init_pins_action_to_this_version_when_writing_workflow(
    run_init, git_repository
):
    run_init("--yes", "--ci", "github")

    workflow = yaml.safe_load(
        (git_repository / ".github" / "workflows" / "rulepack.yml").read_text()
    )
    steps = workflow["jobs"]["lint"]["steps"]
    assert steps[0]["with"]["fetch-depth"] == 0
    assert steps[1]["uses"].startswith("justmatias/rulepack@v")


def test_init_writes_nothing_when_dry_run_is_set(run_init, git_repository):
    completed = run_init("--dry-run", "--pre-commit", "--makefile")

    assert completed.returncode == 0
    assert read_tree(git_repository) == {}
    assert "create           .rulepack.toml" in completed.stderr


def test_init_writes_nothing_when_not_confirmed(run_init, git_repository):
    completed = run_init(answer="n\n")

    assert completed.returncode == 1
    assert read_tree(git_repository) == {}


def test_init_writes_the_plan_when_confirmed(run_init, git_repository):
    completed = run_init(answer="y\n")

    assert completed.returncode == 0, completed.stderr
    assert (git_repository / ".rulepack.toml").is_file()


def test_init_leaves_layout_as_it_is_when_config_exists(run_init, git_repository):
    (git_repository / ".rulepack.toml").write_text('sgconfig = "checks/sg.yml"\n')

    completed = run_init("--yes", "--checks-dir", "lint")

    assert (git_repository / ".rulepack.toml").read_text() == (
        'sgconfig = "checks/sg.yml"\n'
    )
    assert not (git_repository / "lint").exists()
    assert "already exists" in completed.stderr


def test_init_reports_an_error_when_pre_commit_config_is_not_valid_yaml(
    run_init, git_repository
):
    (git_repository / ".pre-commit-config.yaml").write_text("repos:\n  - [unclosed\n")

    completed = run_init("--yes", "--pre-commit")

    assert completed.returncode == 2
    assert "rulepack init:" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_init_creates_local_checks_when_terminal_user_keeps_checks_here(
    run_init_in_terminal, git_repository
):
    exit_code = run_init_in_terminal(answers="y\ny\n")

    assert exit_code == 0
    assert (git_repository / "lint" / "sgconfig.yml").is_file()


def test_init_writes_only_config_when_terminal_user_keeps_checks_elsewhere(
    run_init_in_terminal, git_repository
):
    exit_code = run_init_in_terminal(answers="n\ny\n")

    assert exit_code == 0
    assert list(read_tree(git_repository)) == [".rulepack.toml"]
