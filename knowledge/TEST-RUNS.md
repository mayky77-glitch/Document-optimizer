---
type: test-runs
tags:
  - knowledge/component
  - domain/document-processing
last_verified: 2026-08-16
updated: 2026-08-16
---

# Test runs

Keep only the two latest completed runs relevant to active work.

## 2026-08-16 — low-load real-layout shadow and focused release gate

- A sequential `nice -n 10` shadow used 12 representative sources and one target without applying
  decisions. Nine sources were usable; three remained continuable controlled ambiguities. The
  review contained 2,787 source rows, 984 visible rows, 1,803 hidden zero-activity rows, 280 groups,
  228 families, and 225 packages. No package was auto-safe, no output was created, and all 13 input
  workbooks remained byte-identical.
- Three sources that had previously exceeded the semantic coordinate limit all passed after styled
  empty cells were excluded from that limit.
- The combined source/target/period/service/writer/semantics/UI profile passed `581` tests with one
  environment-gated real-data test skipped in `6.48s`.
- Independent source and service reviews returned `MERGE YES`; no P0/P1 finding remained.

## 2026-08-16 — complete repository gate

- `nice -n 10 .venv/bin/pytest -q` passed `2225` tests and skipped `25` explicit real-data,
  performance, local-model, or fixture-condition opt-ins in `28.07s`.
- `nice -n 10 .venv/bin/ruff check src tests`, `ruff format --check src tests`, and
  `git diff --check` passed.
- GitHub CI run `31949344330` passed its Ruff and test job in `1m41s`. The sole annotation is an
  upstream Node-runtime deprecation notice for standard GitHub Actions, not a repository failure.
- The measured full-suite runtime remains healthy; no proven redundant or useless test was removed.
  Boundary and adversarial tests remain part of the fail-closed contract.

## Knowledge validation

The adaptive-routing validator was run with `--release-check`. It reports no issue for the current
reconciliation cards or maps. The global result remains `INVALID` because unrelated historical task
cards predate the current routing schema and two unrelated historical notes exceed the compactness
limit; migrating that backlog is outside this reconciliation release and no such file was changed.
