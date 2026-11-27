# CHANGELOG

<!-- version list -->

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
