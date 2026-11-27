# CHANGELOG

<!-- version list -->

## v0.6.0 (2026-11-27)

### Documentation

- **specs**: Record the config-only init and close its open question
  ([`3d08a02`](https://github.com/justmatias/rulepack/commit/3d08a023a30421101fae6963aef3a000750576a9))

### Features

- **config**: Default the checks folder to lint/
  ([`9c624fb`](https://github.com/justmatias/rulepack/commit/9c624fb2cdde60c7fd3795c6a75d566774cd0bbb))

- **init**: Ask a person at a terminal whether to keep checks locally
  ([`002975b`](https://github.com/justmatias/rulepack/commit/002975bb788a51a47d0d82ebe35b496f6a2234c3))

- **init**: Write only .rulepack.toml unless --checks-dir is given
  ([`0c95a42`](https://github.com/justmatias/rulepack/commit/0c95a42c915cd7b4c9ca31bd47d16885b8c332f6))

- **lint**: Skip the ast-grep steps when the repo has no local checks
  ([`02a6041`](https://github.com/justmatias/rulepack/commit/02a6041f66629e89e0203252f818ea21f4032902))


## v0.5.0 (2026-11-27)

### Bug Fixes

- **init**: Report a malformed pre-commit config instead of crashing
  ([`a0d3f16`](https://github.com/justmatias/rulepack/commit/a0d3f16949f110bb9eb2ea96ce94855477eb67ed))

### Features

- **init**: Scaffold the rules-as-checks layout with rulepack init
  ([`f4fa135`](https://github.com/justmatias/rulepack/commit/f4fa13520a49ab00ffa8a38e1bc022d9ed94c7eb))

### Refactoring

- **init**: Check the existing layout paths directly
  ([`fc056f5`](https://github.com/justmatias/rulepack/commit/fc056f53a961c8c10e4a8c6c6b5200af82ad230e))


## v0.4.0 (2026-11-26)

### Features

- Publish the checks as pre-commit hooks and a GitHub Action
  ([`aba1b19`](https://github.com/justmatias/rulepack/commit/aba1b19aa8c492485f0aa6f4f629f0bb0902f23d))

### Testing

- Remove the pre-commit hooks tests
  ([`f04f41b`](https://github.com/justmatias/rulepack/commit/f04f41be83d20117db67ab772d751d6740286798))


## v0.3.0 (2026-11-26)

### Features

- **lint**: Run the rule tests, scan and imports with rulepack lint
  ([`7e20ef0`](https://github.com/justmatias/rulepack/commit/7e20ef088fba92cea11482d65fa4bb713099f5c3))

### Refactoring

- **lint**: Name functions for their action and type scan findings
  ([`46f94c7`](https://github.com/justmatias/rulepack/commit/46f94c7f6aa3b9fd4ca9744885742025c538f678))


## v0.2.0 (2026-11-26)

### Refactoring

- Remove the exceptions command
  ([`0cdc857`](https://github.com/justmatias/rulepack/commit/0cdc857e580c18aa8b5824891b665df60d53ebf6))

- **cli**: Import importlib.metadata directly
  ([`c5c5f7d`](https://github.com/justmatias/rulepack/commit/c5c5f7ddc61cc5249e3a759eb589a4705cd80117))

- **config**: Drop the keys that only guards and prose rules read
  ([`811c74c`](https://github.com/justmatias/rulepack/commit/811c74c0f3a28622162f53075facf3f2c43b4932))

- **config**: Read the config file where it is found
  ([`8246789`](https://github.com/justmatias/rulepack/commit/82467892016474432dfdd37896fa2b6ae2fe072e))

- **config**: Split the config module into a package
  ([`6e8f1af`](https://github.com/justmatias/rulepack/commit/6e8f1af45392b03ebe6ee4177db4cfa5d37726a4))


## v0.1.0 (2026-11-26)

- Initial Release
