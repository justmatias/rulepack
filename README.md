# rulepack

Run ast-grep and import-linter checks from shared, versioned rule packs in any repo.

**Status: shared source pinning is available.** Use `rulepack packs` to pin and inspect Git and local sources. Running their checks is the next step in [pack-sources](docs/specs/pack-sources.md). Repos that rely on mstack's bundled checks can keep using mstack `v6.x` in the meantime.

## Why

Agents write more of the code now, and reviewing it means correcting the same preferences again and again: a naming habit, a test layout, an import boundary. If an agent writes the code and you review it, it should write the code the way you would.

Prose rules in Markdown help, but an agent follows them only some of the time. rulepack turns those preferences into static, deterministic checks wherever a check can express them, so a broken rule fails the same way every time and the agent fixes it before you see the diff. Packs make the rules portable: write them once, version them, and select them from any repo.

## Install

You need [`uv`](https://docs.astral.sh/uv/). Once the first release is available on [PyPI](https://pypi.org/project/rulepack/), install the CLI with:

```bash
uv tool install rulepack
```

To run it without installing:

```bash
uvx rulepack --version
```

Until the first PyPI release is available, install from the GitHub release tag:

```bash
uv tool install git+https://github.com/justmatias/rulepack@v0.10.0
```

Or run it without installing:

```bash
uvx --from git+https://github.com/justmatias/rulepack@v0.10.0 rulepack --version
```

## Usage

Scaffold the layout in a repo, then lint it:

```bash
rulepack init --pre-commit --ci github --poe   # shows the plan and asks first
rulepack lint
```

| Command | What it does |
| --- | --- |
| `rulepack init` | Writes `.rulepack.toml`, and with `--checks-dir DIR` an ast-grep sgconfig with empty `rules/` and `rule-tests/` for the repo's own checks. `--pre-commit`, `--ci github` and `--poe` add the hooks, the workflow and the poe tasks (in `pyproject.toml`, or `poe_tasks.toml` when there is none). It shows the plan, asks first (`--yes` skips, `--dry-run` writes nothing) and never overwrites a file, so a second run changes nothing. |
| `rulepack lint` | Runs the checks below. |
| `rulepack config` | Prints the resolved config and where each value comes from (`--json` for JSON). |
| `rulepack hook post-edit`, `rulepack hook stop` | Agent hooks (below). |

### `rulepack lint`

```text
rulepack lint [--changed [--base-ref REF] [--staged] | --files FILE ...]
              [--only STEP ...] [--skip STEP ...] [--json]
```

| Step | Runs | Skipped when |
| --- | --- | --- |
| `test` | `ast-grep test -c <sgconfig> --skip-snapshot-tests` | there is no sgconfig at the default path, or its `testConfigs` hold no test files |
| `scan` | `ast-grep scan -c <sgconfig>`, skipping the `[scan].exclude` globs | there is no sgconfig at the default path, or `--changed` or `--files` selected no file |
| `imports` | `lint-imports` | there is no `.importlinter` (the configured `importlinter`) |

- **Modes.** By default the scan covers the whole repo and warnings don't fail. `--changed` scans only the files changed against `[changed].base_ref` (`--base-ref` overrides it, `--staged` uses the staged files) and passes `--error`, so warnings fail on new or touched code. `--files` scans exactly the given files with `--error` (for pre-commit).
- **All steps run**, even after a failure. The exit code is 1 if any failed, 2 for a usage, config or git error. `--json` prints `{step: {ok, skipped, findings}}`.
- **Tools.** ast-grep and lint-imports come from the environment rulepack runs in. A repo whose `uv.lock` lists import-linter runs its own (`uv run --frozen lint-imports`), because the contracts need the project importable.

### Configuration

Every command reads an optional `.rulepack.toml`, found by walking up from the current directory to the git root. A flag wins over the file, and the file over the defaults. Paths are relative to the file. Unknown keys are an error. rulepack ignores `.mstack.toml`.

```toml
sgconfig = "lint/sgconfig.yml"   # ast-grep config; a missing default means no local checks
importlinter = ".importlinter"   # optional; skipped when missing

[scan]
exclude = []                     # globs every scan skips
extensions = [".py"]             # what --changed, --files and the hooks scan

[hooks]
enabled = true
timeout = 10.0                   # seconds per agent hook run

[changed]
base_ref = "origin/main"
```

### pre-commit

```yaml
repos:
  - repo: https://github.com/justmatias/rulepack
    rev: vX.Y.Z   # a release tag
    hooks:
      - id: rulepack-lint      # ast-grep scan of the staged files; warnings fail too
      - id: rulepack-rules     # rule tests, when a rule or its test changes
      - id: rulepack-imports   # .importlinter contracts
```

`rulepack-imports` needs the project importable: list its third-party packages under the hook's `additional_dependencies`, or run `rulepack lint --only imports` from the project's environment instead.

### GitHub Actions

The action runs the full scan, and on pull requests also the changed-files scan, where warnings fail. Check out with the full history so the base branch exists:

```yaml
steps:
  - uses: actions/checkout@v7
    with:
      fetch-depth: 0
  - uses: justmatias/rulepack@v0.10.0
```

Inputs: `mode` (`full`, `changed` or `both`), `base-ref`, `rulepack-version`, `python-version` and `working-directory`. Every release moves the `v<major>` tag. On other CI providers, run `uvx --from git+https://github.com/justmatias/rulepack@<tag> rulepack lint`, and on merge requests the same with `--changed --base-ref origin/<base branch>`.

### Agent hooks

`rulepack hook post-edit` and `rulepack hook stop` read a Claude Code, Codex or Cursor hook payload on stdin. They run only in repos with `.rulepack.toml`. Post-edit scans the edited files; stop scans the changed files, and reports the same findings only once per session. A run that times out or fails logs a warning and lets the agent continue. Set `[hooks] enabled = false` to turn them off for a repo.

## Pack sources

Declare a Git repository or a local folder in `.rulepack.toml`. Each source
contains a `packs.toml` manifest that lists its packs and checks.

```toml
[sources.mstack]
git = "https://github.com/justmatias/mstack"
ref = "v7.4.0"

[sources.team]
path = "../team-rules"
```

- Run `rulepack packs lock` to pin and fetch Git sources. Commit the generated
  `rulepack.lock` alongside the config. Running it again keeps existing pins
  whose URL and ref still match.
- Run `rulepack packs update` to refresh every Git pin, or
  `rulepack packs update mstack` to refresh only the named source.
- Run `rulepack packs list` to see each source's packs, checks, and locked commit.
  Add `--json` for scripts.

Local sources resolve relative to the config file and need no lock entry.

## Development

```bash
uv sync                     # dev dependencies
uv run pre-commit install   # installs the pre-commit and the commit-msg hooks
uv run poe lint             # every pre-commit hook on every file
uv run poe test             # pytest
```

Planned work lives in [`docs/specs/`](docs/specs/README.md).

## Releasing

Pull requests are squash-merged, so the PR title becomes the commit on `main` and decides the bump: `feat` is a minor bump, `fix` and `perf` a patch, and `!` a major bump once past `1.0` (during `0.x` it bumps the minor version). Other types release nothing.

`release-prepare.yml` commits the bump, `CHANGELOG.md`, `uv.lock` and the tags in this README to the PR branch, so the release is reviewed with the change. After the merge, the `versioning` job in `ci.yml` tags the version, creates the GitHub release and moves the `v<major>` tag.

## Maintaining

GitHub settings, applied with `gh`:

- **Public**, so branch rulesets work on the free plan and consumers can install the CLI and its hooks without a token.
- **Squash merge only.** The squash commit title is the PR title (`COMMIT_OR_PR_TITLE`), and head branches are deleted on merge:

  ```bash
  gh api -X PATCH repos/justmatias/rulepack \
    -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
    -f squash_merge_commit_title=COMMIT_OR_PR_TITLE -f squash_merge_commit_message=COMMIT_MESSAGES \
    -F delete_branch_on_merge=true
  ```

- **A `main` ruleset**: no deletion, no force push, and changes only through a pull request merged with squash:

  ```bash
  gh api -X POST repos/justmatias/rulepack/rulesets --input - <<'EOF'
  {"name": "main", "target": "branch", "enforcement": "active",
   "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
   "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
     {"type": "pull_request", "parameters": {"allowed_merge_methods": ["squash"],
       "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": false,
       "require_code_owner_review": false, "require_last_push_approval": false,
       "required_review_thread_resolution": false}}]}
  EOF
  ```

- **A `GH_TOKEN` secret**: a fine-grained token with contents write access on this repo only. `release-prepare.yml` and `pre-commit-autoupdate.yml` push with it, because a push made with `GITHUB_TOKEN` does not start CI on the pushed commit.

## License

MIT. See [LICENSE](LICENSE).
