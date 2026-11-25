# Pack sources

- **Phase:** next, after the migration
- **Depends on:** [migrate-from-mstack](migrate-from-mstack.md), and mstack's [mstack-uses-rulepack](https://github.com/justmatias/mstack/blob/main/docs/specs/mstack-uses-rulepack.md). Both must have merged: this spec is written against rulepack's own config and code, and mstack must already contain only content.

## Problem

After the migration, `rulepack lint` only runs the checks a repo keeps itself. To share a check, a team copies its YAML into every repo, and the copies drift. mstack's old bundled packs solved this for mstack's own checks only, by shipping them inside the CLI wheel. A check fix needed a CLI release, and nobody else could publish a pack. Repos that used those packs are still on mstack `v6.x`.

## Goal

A repo lists one or more **sources**, git repos or local folders, and selects packs from them in `.rulepack.toml`. A checked-in lockfile pins each source. `rulepack lint` runs the selected packs' checks and rule tests next to the repo's own. No pack content ships inside rulepack.

## Out of scope

- A registry or index of public packs. A source is a git URL or a path.
- Rewriting check IDs (see "ID clashes").

## Design

**Source manifest.** Any repo or folder with a `packs.toml` at its root is a source:

```toml
# Optional. These are the defaults.
checks_dir = "lint/rules"
tests_dir = "lint/rule-tests"

[packs.python-core]
checks = ["no-bare-except", "no-swallowed-exception"]
```

Every path the manifest names must resolve inside the source root, or loading fails. The manifest is validated where it is read and trusted after that. A pack lists checks only. Its prose is verified by `rulepack coverage` in the source repo, and a consumer's coverage checks only the consumer's own prose. A consumer's prose may name a pack check in `enforced-by:`, and coverage resolves that ID against the selected packs.

**Consumer config.**

```toml
packs = ["mstack/python-core", "mstack/testing", "team/backend"]

[sources.mstack]
git = "https://github.com/justmatias/mstack"
ref = "vX.Y.Z"          # tag, branch or SHA; the lock pins the commit

[sources.team]
path = "../team-rules"  # relative to the config file

[pack_overrides]
disable = ["no-manual-init-boilerplate"]
severity = { no-sleep-in-tests = "warning" }
```

A source has exactly one of `git` or `path`, and packs are always selected as `<source>/<pack>`. There is no implicit default source: rulepack names no content repo.

**Lockfile.** `rulepack packs lock` resolves each git source's `ref` to a commit and writes `rulepack.lock` next to the config. Each entry records `git`, `ref` and `commit`.
- `rulepack lint` never writes the lock. It fails when a git source is missing from the lock, or when its `git` or `ref` differs from the config, and the message says to run `rulepack packs lock`.
- `rulepack packs update [<source>...]` re-resolves refs and rewrites the lock.
- Path sources are not locked. `lint --changed` warns in CI when a selected pack comes from a path outside the repo.

**Cache.** Sources live in `$XDG_CACHE_HOME/rulepack/sources/<sha256 of url>/<commit>/`. Each commit is extracted with `git archive` from a `--filter=blob:none` clone, into a temporary folder that is then renamed into place. An interrupted fetch never leaves a partial commit, and a rerun fetches only what is missing. git's own credentials cover private sources, and rulepack stores none.

**Agent hooks never fetch.** If a locked commit is not cached, `rulepack hook` skips pack checks for that run and logs one line saying to run `rulepack packs lock`, which also fetches. `rulepack lint` fetches when it needs to.

**Host defaults.** `$XDG_CONFIG_HOME/rulepack/config.toml` may hold `packs` and `[sources]`, with a lock next to it written by `rulepack packs lock --host`. Host defaults apply only when a repo has no `.rulepack.toml`. A repo's `packs` replaces them. They exist so agent hooks can check repos that have no config, and CI never reads them.

**ID clashes.** Existing `ast-grep-ignore: <id>` comments and `[pack_overrides]` use bare IDs, so IDs are never rewritten.
- A repo's own check wins over a pack check with the same ID, and rulepack logs it.
- Two selected packs that define the same ID is an error naming both sources.

**`rulepack packs list`** lists every declared source's packs and checks, with each source's locked commit. `--json` gives the same data for scripts.

**mstack becomes a source.** mstack adds a `packs.toml` in this format, which lists checks only, as a small PR in mstack released as a minor version. This repo then replaces the bootstrap's pinned mstack `v6.7.1` hooks with `[sources.mstack]` and lints itself with its own code.

## Changes

- `src/rulepack/packs.py`: manifest and source models, path containment, resolution, cache, lock read and write, and the `lock`, `update` and `list` subcommands.
- `config.py`: `packs`, `sources`, `[pack_overrides]`, host config.
- `lint.py`: pack checks and pack rule tests next to local ones, a temporary sgconfig, overrides, and the clash rules.
- `hooks.py`: skip uncached sources.
- `coverage.py`: resolve `enforced-by:` against pack checks.
- `init.py` and its templates: `--source <name>=<git url>@<ref>` writes a `[sources]` block and the lock.
- This repo's `.rulepack.toml`, `rulepack.lock` and `.pre-commit-config.yaml`: self-lint through `[sources.mstack]`.
- In mstack: `packs.toml`.

## Tests

Every git test uses a local bare repo created in `tmp_path` as the source URL, so no test reaches the network.

- A consumer with a git source and a lock fails `lint` on a violating file, and passes once the check is disabled.
- A path source works with no lock entry.
- A missing lock, and a lock whose `ref` differs from the config, each fail with the `packs lock` message, and `lint` leaves the lock untouched.
- Running `packs lock` twice writes identical files. After a new commit on the source's branch, `packs update` moves the pin.
- A manifest path that escapes the source root is rejected.
- Two packs with the same check ID fail and name both sources. A local check with a pack check's ID wins and is logged.
- The post-edit hook with an uncached commit runs local checks, skips pack checks, and clones nothing.
- With host defaults set, a repo without `.rulepack.toml` gets those packs in hooks, and `lint` in a repo with `.rulepack.toml` ignores them.
- The built wheel contains no `.yml` or `.mdc` content.

## Docs

- `README.md`: sources, the lock, `packs lock`, `packs update` and `packs list`, overrides, host defaults, pinning. Also a migration section for repos coming from mstack `v6.x` packs, mapping bare pack names to `mstack/<name>` plus the `[sources.mstack]` block.
- In mstack: the `sync` skill and `authoring-a-check.md` prefer selecting a pack over copying a check.

## Acceptance criteria

- [ ] A repo runs checks from mstack and from a second git repo, pinned by a checked-in lock, in CI with nothing but `uvx rulepack`.
- [ ] A check fix in a source reaches a consumer through `rulepack packs update`, with no rulepack release.
- [ ] rulepack lints itself through `[sources.mstack]`, and its `.pre-commit-config.yaml` no longer names mstack.
- [ ] Agent hooks never touch the network.

## Open questions

- Whether `ref` should reject branch names, to discourage moving refs. The lock pins either way.
