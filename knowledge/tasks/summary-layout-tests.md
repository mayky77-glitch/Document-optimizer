---
type: task
status: done
work_id: drawing-card-summary-layout-v2
role: worker
agent_role: tester
owner: "summary-layout-tester"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: "sha256:54571e99d3eeccef921fbaabd5006167c4fd90e0ee530bc0a8d10871d38945d4"
no_progress_count: 0
circuit_state: closed
routing_reason: "Formula, sheet-title, styling and UI contract regressions"
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
  - "tests/integration/test_drawing_card_ui_contract.py"
  - "tests/integration/test_drawing_card_real_data.py"
source_paths:
  - "tests/unit/drawing_card/test_summary_report.py"
  - "tests/integration/test_drawing_card_ui_contract.py"
  - "tests/integration/test_drawing_card_real_data.py"
depends_on:
  - "summary-layout-xlsx"
  - "summary-layout-ui"
tags:
  - "task/implementation"
  - "status/done"
  - "drawing-card"
  - "tests"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Регрессии нового XLSX и UI layout

## Goal

Lock the horizontal XLSX summary and compact UI regression contracts without
changing production code.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `tests/unit/drawing_card/test_summary_report.py`
  - `tests/integration/test_drawing_card_ui_contract.py`
- Commands and tests run:
  - `PYTHONPATH=src ./.venv/bin/pytest -q tests/unit/drawing_card/test_summary_report.py tests/integration/test_drawing_card_ui_contract.py tests/integration/test_drawing_card_real_data.py` — 9 passed, 1 skipped (real-source environment variable absent).
  - `./.venv/bin/ruff check tests/unit/drawing_card/test_summary_report.py tests/integration/test_drawing_card_ui_contract.py tests/integration/test_drawing_card_real_data.py` — passed.
  - `node --check src/report_processor/admin_panel/assets/drawing-card-review.js` — passed.
  - `git diff --check` — passed.
  - `PYTHONPATH=src ./.venv/bin/pytest -q` — 753 passed, 22 skipped.
- Result:
  - Replaced the obsolete vertical A:E summary assertion with a strict four-card contract for three indexes: A1, G1, A12, and separate `Все индексы` at G12.
  - Tests require all eight categories per card, merged/styled titles and headers, quoted `Карточка остатков` source formulas, total formulas that sum index-card cells, `#,##0.000` cost format, calculation flags, and the existing 3-of-4 template-slot trim validation.
  - UI contract now checks bounded desktop columns, one compact Apply/Reject row, and both responsive wrapping states while retaining the API mapping test.
- Risks or follow-up:
  - The immutable real-data smoke remains skipped until `DOCUMENT_OPTIMIZER_DRAWING_CARD_REAL_SOURCE_XLSX` is supplied; synthetic and full-suite contracts are green.

## Knowledge delta

- Summary layout consumers must use card coordinates rather than the former vertical table rows: with three indexes, index cards begin at A1, G1, A12 and the total card begins at G12.

## Handoff

Accepted after focused checks and the full `753 passed, 22 skipped` gate.
