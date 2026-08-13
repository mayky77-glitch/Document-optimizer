---
type: test-runs
tags:
  - knowledge/component
  - domain/document-processing
last_verified: 2026-08-13
updated: 2026-08-13
---

# Test runs

Keep only the two latest completed runs relevant to active work.

## 2026-08-13 — lifecycle release and test portfolio

- Accepted lifecycle integration: `c8da7108b5c0dd228d5ef5eb1fee2568cdcca3b8`.
- Full command: `uv run --extra dev pytest -q`.
- Result: `1754 passed, 25 skipped in 29.74s`.
- Lifecycle focused release: `70 passed`; Ruff, format and diff checks passed.
- Exact-once apply binds immutable inputs, one output inode/digest/mode, canonical decisions and
  one SQLite marker. Restart rebuilds replay from uploads plus the atomic decision snapshot;
  manifests contain no workbook-derived work/unit values.
- No useless tests were found. Two 1,001-row DuckDB tests protect different APIs; a shared
  read-only session seed cuts their combined setup by roughly 3–7 seconds without weakening the
  1000/1001 boundary.

## 2026-08-13 — real target/reference shadow

- Twelve original sources, one clean target and one desired reference were inspected from immutable
  copies; every input hash stayed unchanged and every formula cell had a cached value.
- Clean/reference comparison: 180 rows in both; width 15→17; J/K unchanged; one adjacent
  reporting-period pair appears in L/M; the narrative block shifts two columns right; only the
  selected stage gains period values.
- Current runtime cannot complete this shadow: merged-header candidate construction reports false
  ambiguity and the valid full dotted target identifier is rejected. These are RA-019—RA-021 in
  [[tasks/reconciliation-real-layout-gate0|Real-layout Gate 0]].

## Knowledge validation

Global validator remains `INVALID` because many historical task cards predate the current schema.
New and changed cards/links are checked separately; historical vault migration is outside this
accuracy remediation.
