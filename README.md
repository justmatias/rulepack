# rulepack

Run ast-grep and import-linter checks from shared, versioned rule packs in any repo.

A repo runs its own checks and the checks of **packs** it selects from **sources**: git repos or local folders with a `packs.toml`. A checked-in `rulepack.lock` pins each git source, so a check fix reaches a repo through `rulepack packs update`, without a rulepack release. No check ships inside rulepack.

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
uv tool install git+https://github.com/justmatias/rulepack@v0.8.0
```

Or run it without installing:

```bash
uvx --from git+https://github.com/justmatias/rulepack@v0.8.0 rulepack --version
```


## Usage

Scaffold the layout in a repo, then lint it:

```bash
rulepack init --pre-commit --ci github --makefile   # shows the plan and asks first
rulepack lint
```

| Command | What it does |
| --- | --- |
| `rulepack init` | Writes `.rulepack.toml`, and with `--checks-dir DIR` an ast-grep sgconfig with empty `rules/` and `rule-tests/` for the repo's own checks. `--pre-commit`, `--ci github` and `--makefile` add the hooks, the workflow and the Make targets, and `--source NAME=URL@REF` declares a pack source and locks it. It shows the plan, asks first (`--yes` skips, `--dry-run` writes nothing) and never overwrites a file, so a second run changes nothing. |
| `rulepack lint` | Runs the checks below. |
| `rulepack config` | Prints the resolved config and where each value comes from (`--json` for JSON). |
| `rulepack packs lock`, `update`, `list` | Pin, update and list the pack sources (below). |
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

Every command reads an optional `.rulepack.toml`, found by walking up from the current directory to the git root. A flag wins over the file, and the file over the defaults. Paths are relative to the file. Unknown keys are an error. rulepack ignores `.mstack.toml`, except that one with lint keys and no `.rulepack.toml` is an error that says to rename it.

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

### Pack sources

Any git repo or folder with a `packs.toml` at its root is a source:

```toml
# Optional. These are the defaults, relative to the source root.
checks_dir = "lint/rules"
tests_dir = "lint/rule-tests"

[packs.python-core]
checks = ["no-bare-except", "no-swallowed-exception"]
```

Each check is `<checks_dir>/<id>.yml`, and its rule tests, when the source has them, are `<tests_dir>/<id>-test.yml`. Every path must stay inside the source.

A repo declares sources and selects packs as `<source>/<pack>`. There is no default source:

```toml
packs = ["mstack/python-core", "mstack/testing", "team/backend"]

[sources.mstack]
git = "https://github.com/justmatias/mstack"
ref = "vX.Y.Z"           # a tag, branch or SHA; the lock pins the commit

[sources.team]
path = "../team-rules"   # relative to this file; not locked

[pack_overrides]
disable = ["no-manual-init-boilerplate"]
severity = { no-sleep-in-tests = "warning" }
```

- `rulepack packs lock` resolves each new or changed git source to a commit, writes `rulepack.lock` next to the config, and fetches it. Running it again changes nothing. Commit the lock.
- `rulepack packs update [SOURCE ...]` re-resolves the refs (all sources by default) and rewrites the lock. Pin a tag or a SHA, so `update` is the only thing that moves a source.
- `rulepack packs list [--json]` lists each source's packs, checks and locked commit.
- `rulepack lint` runs the packs' checks and rule tests next to the repo's own. It fetches a locked commit when the cache lacks it, and never writes the lock: a git source missing from the lock, or whose `git` or `ref` changed, fails with a message to run `rulepack packs lock`. `--changed` in CI warns about a path source outside the repo.
- A repo's own check wins over a pack check with the same ID, and lint says so. Two selected packs with the same ID is an error that names both sources. IDs are never rewritten, so `ast-grep-ignore: <id>` and `[pack_overrides]` use bare IDs.
- Sources are cached in `$XDG_CACHE_HOME/rulepack/sources/`, one extracted folder per commit. git's own credentials reach private sources; rulepack stores none.

**Host defaults.** `$XDG_CONFIG_HOME/rulepack/config.toml` may hold `packs` and `[sources]`, locked with `rulepack packs lock --host` (run outside a configured repo). They apply only in repos without `.rulepack.toml`, so agent hooks can check those too. A repo's config replaces them, and CI never reads them.

**Agent hooks never fetch.** When a locked commit is not cached, the hook runs the repo's own checks, skips the pack checks, and logs one line saying to run `rulepack packs lock`.

### Migrating from mstack v6 packs

Rename `.mstack.toml` to `.rulepack.toml`, change each bare pack name to `mstack/<name>` (`python-core` becomes `mstack/python-core`), add the source, and lock it:

```toml
packs = ["mstack/python-core", "mstack/testing"]

[sources.mstack]
git = "https://github.com/justmatias/mstack"
ref = "vX.Y.Z"   # an mstack release with packs.toml
```

```bash
rulepack packs lock
git add .rulepack.toml rulepack.lock
```

Then switch the pre-commit `repo:` and the Action from mstack to rulepack, with `rulepack-*` hook ids.

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
  - uses: justmatias/rulepack@v0.8.0
```

Inputs: `mode` (`full`, `changed` or `both`), `base-ref`, `rulepack-version`, `python-version` and `working-directory`. Every release moves the `v<major>` tag. On other CI providers, run `uvx --from git+https://github.com/justmatias/rulepack@<tag> rulepack lint`, and on merge requests the same with `--changed --base-ref origin/<base branch>`.

### Agent hooks

`rulepack hook post-edit` and `rulepack hook stop` read a Claude Code, Codex or Cursor hook payload on stdin. They run only in repos with `.rulepack.toml`, or in any git repo when host defaults are set (see Pack sources). Post-edit scans the edited files; stop scans the changed files, and reports the same findings only once per session. A run that times out or fails logs a warning and lets the agent continue. Set `[hooks] enabled = false` to turn them off for a repo.

## Development

```bash
make setup                  # dev dependencies
uv run pre-commit install   # installs the pre-commit and the commit-msg hooks
make lint                   # every pre-commit hook on every file
make test                   # pytest
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
