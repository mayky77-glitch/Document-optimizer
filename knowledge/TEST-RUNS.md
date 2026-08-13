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

## 2026-08-13 — user-facing verification audit

- Product commit: `7aa8d30e5abbd49b6d5b9e76b03122c0f447f51e`; no production/test edits.
- Command: `uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/excel_writer/test_row_annotations.py tests/integration/test_block18_admin_panel.py`.
- Result: `35 passed in 0.19s`.
- Direct representative checks: all 12 source style tables reproduce `STYLES_MISSING`; one
  current-layout verify would check/red 13 rows versus 3 under independently bound cumulative
  semantics, with 10 current-only red rows. Source and target digests stayed unchanged.
- Additional deterministic probes: missing target stage produced empty catalog and 13/13 would-fail
  rows; duplicate source SHA produced 26 canonical rows and 13 two-member groups.
- Interpretation: green synthetic tests do not cover the real style shape, alternate cumulative
  header, empty stage, duplicate SHA or numeric equality.

## 2026-08-12 — full repository gate and adjacent reconciliation evidence

- Product commit: `30eeafade56658d46a022eae00f5cf59928a3a55`; product source remained identical at
  `7aa8d30e5abbd49b6d5b9e76b03122c0f447f51e` because intervening commits are knowledge-only.
- Command: `uv run --extra dev pytest -q`.
- Result: `1667 passed, 25 skipped in 29.25s`.
- Focused reconciliation gate: `327 passed, 3 skipped, 1362 deselected`; specialist sets also
  passed.
- Representative adjacent run: 12 immutable inputs, 2,953 extracted rows and a verified output;
  independent inspection proved one correct Decimal path and the RA-001 wrong-output path.
- Interpretation: repository regressions are green, but opt-in real-data coverage and missing
  adversarial fixtures leave material accuracy gaps.

## Knowledge validation

Global validator remains `INVALID` because many historical task cards predate the current schema
(invalid statuses/routes/fingerprints and oversized notes). The two defects introduced during this
audit (one draft-card status and one wiki link) were corrected. New/changed wiki links are checked
separately before handoff; historical vault migration is outside this audit scope.
