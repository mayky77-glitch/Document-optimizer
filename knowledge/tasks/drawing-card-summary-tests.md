---
type: task
status: done
work_id: drawing-card-summary-v1
role: worker
agent_role: tester
owner: "summary-tester"
profile: L1
routing_grade: P3
progress_revision: 2
state_fingerprint: "sha256:cd2fbd23a94568cf8d2b52fe6fc74969eed41f36a3b74290dd31c02e500f915b"
no_progress_count: 0
circuit_state: closed
routing_reason: "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 formulas, OOXML, Decimal totals and layout regression"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-01
updated: 2026-08-01
write_scope:
  - "tests/unit/drawing_card/test_summary_report.py"
  - "tests/integration/test_drawing_card_real_data.py"
  - "tests/integration/test_drawing_card_admin.py"
  - "tests/integration/test_drawing_card_ui_contract.py"
source_paths:
  - "tests/unit/drawing_card/test_summary_report.py"
  - "tests/integration/test_drawing_card_real_data.py"
depends_on:
  - "drawing-card-summary-production"
  - "drawing-card-summary-ui"
tags:
  - "task/implementation"
  - "status/done"
  - "drawing-card"
  - "tests"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Регрессии сводного Excel-отчета

## Goal

Cover publication and UI acceptance contracts without modifying production code.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `tests/unit/drawing_card/test_summary_report.py`,
  `tests/integration/test_drawing_card_admin.py`,
  `tests/integration/test_drawing_card_ui_contract.py`.
- Commands and tests run:
  `uv run --extra dev pytest tests/unit/drawing_card/test_summary_report.py tests/integration/test_drawing_card_real_data.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_ui_contract.py`;
  `uv run --extra dev ruff check tests/unit/drawing_card/test_summary_report.py tests/integration/test_drawing_card_real_data.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_ui_contract.py`;
  `node --check src/report_processor/admin_panel/assets/drawing-card.js`;
  `node --check src/report_processor/admin_panel/assets/drawing-card-review.js`;
  `git diff --check`.
- Result: 28 passed, 1 skipped (the optional real-data source environment variable is
  unset); Ruff, both Node syntax checks, and diff validation passed. The unit
  contract verifies 3-of-4 template-slot trim, 8 rows for each of three indexes
  plus 8 `Все индексы` rows, `SUMIF` formulas, automatic/full calculation
  flags, `#,##0.000` cost formatting, and `validate_card == OK`. It also proves
  mixed units reject publication with `SUMMARY_MIXED_UNIT`. Follow-up focused
  unit coverage is 5 passed: a missing unit on one index rejects publication
  with `SUMMARY_MISSING_UNIT`, while incompatible units across indexes reject
  it with `SUMMARY_MIXED_UNIT`; both leave no output file. Static UI tests
  verify direct persistent dark theme, `aria-pressed`, one unified action row,
  no legacy duplicate approve/reject controls, and the `approve` /
  `change_category` / `cost_only` / `reject` request mapping.
- Risks or follow-up: `test_drawing_card_real_data.py` remains skipped until
  `DOCUMENT_OPTIMIZER_DRAWING_CARD_REAL_SOURCE_XLSX` points at an approved
  workbook; the static UI contract does not replace browser interaction testing.
  Global knowledge validation remains blocked by pre-existing historical cards;
  filtering its output produced no error for this card.

## Proposed knowledge delta

- The drawing-card summary contract is now protected by deterministic workbook
  publication checks; UI state and action mapping have a source-level contract
  while end-to-end browser coverage remains a follow-up.

## Handoff

Accepted: focused regressions and full `752 passed, 22 skipped` gate completed.
