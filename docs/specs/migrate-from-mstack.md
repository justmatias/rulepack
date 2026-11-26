# Migrate the linter from mstack

- **Phase:** next
- **Depends on:** the bootstrap (`build/bootstrap-repository`), which gives this repo its packaging, CI, pre-commit and releases.
- **Runs in parallel with:** mstack's [mstack-uses-rulepack](https://github.com/justmatias/mstack/blob/main/docs/specs/mstack-uses-rulepack.md). This spec adds the code here, and that one deletes it from mstack and switches mstack to `rulepack`. They merge back to back (see "Cutover"), so neither repo carries dead code or a second copy for longer than the gap between two merges.

## Problem

All of the enforcement logic lives in mstack's `src/mstack/`: the ast-grep scan, rule tests, import-linter, changed-file scans, prose/check coverage, the exception budget, domain-check, commit-message checks, agent hooks and `init`. mstack is meant to keep only content: prose rules, ast-grep checks and skills. Until the code moves, every linter fix is an mstack release, and the linter cannot grow as a tool of its own.

## Goal

`rulepack` runs everything `mstack lint` runs today against a repo's own checks, from `.rulepack.toml`, with the moved files' history. `v0.1.0` releases it, and mstack's cleanup PR switches to it right after.

## Out of scope

- **Shared packs.** mstack's bundled packs (`packs.py`, `packs.toml`, `packs`, `[pack_overrides]`, host default packs) are not migrated. They come back as [pack-sources](pack-sources.md), which loads packs from any source. Moving the bundled version would mean moving code that this spec's successor deletes.
- New features. Behavior is the same as `mstack lint` at the last mstack release, minus packs.

## Design

**What moves.** Paths are under `src/mstack/` in mstack and under `rulepack/` here.

| From mstack | Here | Command |
| --- | --- | --- |
| `lint.py`, without the pack code (`pack_rules`, `packed_run`, `write_pack_*`, `--packs`) | `lint.py` | `rulepack lint` (`--changed`, `--staged`, `--files`, `--only`, `--skip`, `--json`) |
| `changed_files.py`, `project_paths.py` | same | |
| `config.py`, without `packs`, `pack_overrides` and `HostConfig` | `config.py` | `rulepack config` |
| `init.py`, `templates/`, without the `packs` line | same | `rulepack init` |
| `hooks.py` | same | `rulepack hook post-edit`, `rulepack hook stop` |
| `guards/check_exceptions.py` | `exceptions.py` | `rulepack exceptions` |
| `guards/check_rule_coverage.py`, without `pack_coverage` | `coverage.py` | `rulepack coverage` |
| `guards/check_domain.py`, `generic_names.txt` | `domain_check.py`, same | `rulepack domain-check` |
| `guards/credit.py`, `render.split_frontmatter` | `credit.py`, `frontmatter.py` | |
| `action.yml`, `.pre-commit-hooks.yaml` | same, with `rulepack-*` hook IDs | |
| their tests, `fixtures/` used by them | `tests/`, `tests/fixtures/` | |

**Prose is in scope.** `coverage` reads each prose rule's frontmatter (`enforced-by`, `globs`, credit) to prove that rules and checks point to each other. So rulepack reads `.mdc` frontmatter. It never renders or installs prose; that stays in mstack. `split_frontmatter` and `credit_problems` exist in both repos, about 40 lines each side. A shared library for that much code would be a third package to release.

**Config.** `.rulepack.toml` has the same keys as `.mstack.toml` today, minus the pack keys: `rules_dir`, `sgconfig`, `importlinter`, `pre_commit_config`, `[scan]`, `[hooks]`, `[domain_check]`, `[changed]`. `[commits]` stays in mstack with its commit-message check. The lookup and precedence rules are the same: defaults, then the file, then flags. `rulepack` ignores `.mstack.toml`. A repo that still has one with lint keys gets an error that tells it to rename the file.

**Agent hooks** run in repos with `.rulepack.toml`, where they previously needed `.mstack.toml`.

**History.** Run `git filter-repo` over a clone of mstack, keeping only the moved paths, then merge into `main` with `--allow-unrelated-histories`. The package and import rename (`mstack` → `rulepack`) is one commit on top, and the removal of the pack code is another. This keeps blame readable and the deleted code visible in the history.

**Dogfooding.** Until [pack-sources](pack-sources.md) ships, this repo cannot load mstack's checks from a source. It keeps the bootstrap's pinned mstack `v6.7.1` hooks for its own Python checks; that tag still ships bundled packs. Copying the checks here would be exactly the drift packs exist to prevent. Commit messages stay on mstack's `commit-msg` hook: rulepack does not reimplement it.

**CI.** Add these jobs and steps to the bootstrap's CI:
- `action-self-test`, running `./` on a fixture repo.
- The slow `pre-commit try-repo` tests.
- A `make demo` equivalent: the scan over `tests/fixtures/invalid/` must fail.
- `uv run rulepack lint` in the portability matrix.

**Cutover**, the order of merges between the two repos:
1. Open this PR (`feat: move the linter from mstack`) and mstack's cleanup PR together. While both are open, mstack's PR pins rulepack to this PR's head commit, so its CI runs the real code.
2. **Parity check before merging:** on mstack's repo, `mstack lint --json` at mstack's `main` and `rulepack lint --json` on mstack's PR branch report the same findings.
3. Merge this PR. CI tags `v0.1.0` and moves `v0`.
4. Change mstack's pin to `v0.1.0` and merge mstack's PR.

**Consumers that select packs** (`packs = [...]` in `.mstack.toml`) have no rulepack equivalent until [pack-sources](pack-sources.md). Until then they stay on mstack `v6.x` in pre-commit and CI. The README says so.

## Changes

- `rulepack/`: the modules above. `cli.py` gets the full command table, replacing the bootstrap's stub.
- `tests/`, including `tests/fixtures/` (valid and invalid samples).
- `pyproject.toml`:
  - runtime dependencies: `ast-grep-cli` (pinned to a minor range), `import-linter`, `pydantic`, `pyyaml`
  - the `slow` marker, and `fixtures/` excludes for ruff, pylint and mypy
- `uv.lock`, and the pylint and mypy `additional_dependencies` in `.pre-commit-config.yaml`.
- `action.yml`, `.pre-commit-hooks.yaml`, `.github/workflows/ci.yml`.
- `README.md`: usage (`init`, `lint`, config keys, CI, the Action, pre-commit, agent hooks). The status line now says "no shared packs yet".

## Tests

- The moved test suite passes under the new name, with no test reaching the network.
- `rulepack lint` on `tests/fixtures/invalid/` fails, and on `tests/fixtures/valid/` passes.
- A repo with `.mstack.toml` lint keys and no `.rulepack.toml` gets the rename message.
- `rulepack hook post-edit` with a Claude Code payload and with a Codex payload lints the edited file. Without `.rulepack.toml`, it does nothing.
- The Action self-test and the `pre-commit try-repo` tests run on a clean runner.
- The parity check in "Cutover" step 2, recorded in the PR.

## Docs

- `README.md` (above).
- `docs/specs/README.md`: remove this row and point at `pack-sources` as next.

## Acceptance criteria

- [ ] `v0.1.0` is tagged. `uvx --from git+https://github.com/justmatias/rulepack@v0.1.0 rulepack lint` gives the same findings on mstack as `mstack lint` did.
- [ ] `git log --follow rulepack/lint.py` reaches the file's history in mstack.
- [ ] No code here refers to packs.
- [ ] mstack's cleanup PR merges on `v0.1.0`.

## Open questions

- Whether `rulepack init` keeps scaffolding a prose rules folder, or leaves prose to mstack's `sync` skill and only writes `.rulepack.toml`, the sgconfig and CI.
