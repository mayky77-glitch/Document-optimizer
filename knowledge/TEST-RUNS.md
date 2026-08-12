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

## 2026-08-12 — reconciliation baseline

- Commit: `8d87a2c96ec3a26b3263cbff157755d18d07ec05`.
- Command: `uv run pytest -q -k reconciliation`.
- Result: `327 passed, 3 skipped, 1362 deselected in 4.65s`.
- Skips: environment-gated package real data, reconciliation real data and local RAG model.
- Interpretation: synthetic/contract reconciliation baseline is green; skipped real-data
  coverage must be replaced by direct local workbook evidence in the active audit.
