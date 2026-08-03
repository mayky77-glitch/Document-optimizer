---
type: task
status: done
work_id: drawing-card-contract-check-rag-v1
role: worker
agent_role: worker
owner: "contract-output-tester"
profile: L1
routing_grade: P3
progress_revision: 4
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent regression coverage for workbook semantics and persisted review feedback"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - "tests/unit/drawing_card"
  - "tests/unit/admin_panel/test_drawing_card_service.py"
  - "tests/integration/test_drawing_card_real_data.py"
  - "tests/integration/test_drawing_card_admin.py"
source_paths:
  - "tests/unit/drawing_card"
  - "tests/unit/admin_panel/test_drawing_card_service.py"
  - "tests/integration/test_drawing_card_real_data.py"
  - "tests/integration/test_drawing_card_admin.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Проверить новые поля, расхождения и RAG feedback

## Goal

Add independent contract-output and RAG-feedback regressions without changing production code.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `tests/unit/drawing_card/test_hierarchy_aggregates.py`
  - `tests/unit/drawing_card/test_inline_review_flow.py`
  - `tests/unit/drawing_card/test_summary_report.py`
  - `tests/unit/admin_panel/test_drawing_card_service.py`
- Commands and tests run:
  - `.venv/bin/pytest -q tests/unit/drawing_card/test_hierarchy_aggregates.py tests/unit/drawing_card/test_inline_review_flow.py tests/unit/admin_panel/test_drawing_card_service.py` — `28 passed in 0.19s`.
  - `.venv/bin/ruff check tests/unit/drawing_card/test_hierarchy_aggregates.py tests/unit/drawing_card/test_inline_review_flow.py tests/unit/admin_panel/test_drawing_card_service.py` — `All checks passed!`.
  - `.venv/bin/pytest -q tests/unit/drawing_card/test_summary_report.py tests/unit/drawing_card/test_hierarchy_aggregates.py tests/unit/drawing_card/test_inline_review_flow.py tests/unit/admin_panel/test_drawing_card_service.py` — `10 failed, 28 passed` after output code arrived.
  - `.venv/bin/pytest -q tests/unit/drawing_card/test_summary_report.py tests/unit/drawing_card/test_hierarchy_aggregates.py tests/unit/drawing_card/test_inline_review_flow.py tests/unit/admin_panel/test_drawing_card_service.py` — `38 passed in 2.41s` after the targeted expectation updates and output fixes.
  - `.venv/bin/ruff check tests/unit/drawing_card/test_summary_report.py tests/unit/drawing_card/test_hierarchy_aggregates.py tests/unit/drawing_card/test_inline_review_flow.py tests/unit/admin_panel/test_drawing_card_service.py` — `All checks passed!`.
  - `git diff --check` — clean.
- Result:
  - New tests prove cached formula values, empty-as-zero new metrics, separate quantity/cost source sets, feedback snapshot lifecycle, workbook columns/scaling, tolerance boundary, targeted highlight, and internal hyperlink registry.
  - Existing exact feedback tests already prove normalized name+unit replay and different-unit manual isolation.
- Risks or follow-up:
  - Initial output defects were fixed by the developer; stale test expectations were updated to the public 10-column layout and openpyxl numeric reload semantics.
  - Real external XLSX fixture is opt-in and unavailable in this run; committed synthetic fixture covers dual formula/cached values but not every physical production schema or duplicate contract leaf-column arrangement.

## Handoff

Accepted. Real-data environment test remains unavailable; synthetic fixtures and focused regressions pass.
