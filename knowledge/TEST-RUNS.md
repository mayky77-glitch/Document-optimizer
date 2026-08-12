---
type: test-runs
tags:
  - knowledge/component
  - domain/document-processing
last_verified: 2026-08-12
updated: 2026-08-12
---

# Test runs

Keep only the two latest completed runs relevant to active work.

## 2026-08-12 — full repository gate after audit evidence

- Commit: `30eeafade56658d46a022eae00f5cf59928a3a55` plus knowledge-only working changes.
- Command: `uv run --extra dev pytest -q`.
- Result: `1667 passed, 25 skipped in 29.25s`.
- Interpretation: the repository regression gate is green. Environment-gated real-data tests
  remain skipped; direct local workbook evidence independently exposes RA-001.

## 2026-08-12 — reconciliation audit focused gates

- Commit: `30eeafade56658d46a022eae00f5cf59928a3a55`.
- Command: `uv run --extra dev pytest -q -k reconciliation`.
- Result: `327 passed, 3 skipped, 1362 deselected in 4.39s`.
- Additional focused ingestion/grouping/state/writer set: `92 passed in 0.27s`.
- Representative workbook run: 12 immutable inputs, 2,953 extracted rows, verified output;
  independent original/result inspection proved one correct row and RA-001 wrong-output path.
- Interpretation: existing tests are green but do not cover the real alternate cumulative
  layout; product accuracy is blocked despite the green suite.
