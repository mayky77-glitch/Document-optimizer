---
type: task
status: done
work_id: drawing-card-million-values-v3
role: worker
agent_role: tester
owner: "million-feedback-tester"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: "million-feedback-regressions"
no_progress_count: 0
circuit_state: closed
routing_reason: "Cross-contract regression checks after three bounded production changes"
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
  - "tests/unit/drawing_card"
  - "tests/unit/stage_rag"
  - "tests/unit/admin_panel"
  - "tests/integration/test_drawing_card_admin.py"
source_paths:
  - "tests/unit/drawing_card/test_summary_report.py"
  - "tests/integration/test_drawing_card_ui_contract.py"
  - "tests/unit/drawing_card"
  - "tests/unit/stage_rag"
  - "tests/unit/admin_panel"
  - "tests/integration/test_drawing_card_admin.py"
depends_on:
  - "million-values-xlsx"
  - "review-wrap-ui"
  - "feedback-rule-reuse"
tags:
  - "task/implementation"
  - "status/done"
  - "drawing-card"
  - "tests"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Регрессии миллионов, literal summary и feedback reuse

## Goal

Add regression coverage for literal million-ruble workbooks, legacy update units, formula-free summaries, responsive decision controls, and latest local exact-feedback precedence including reject-without-review replay.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `tests/unit/drawing_card/test_summary_report.py`, `tests/unit/drawing_card/test_inline_review_flow.py`, `tests/unit/drawing_card/test_drawing_card_service_contract.py`, `tests/integration/test_drawing_card_ui_contract.py`.
- Commands and tests run: 20 focused drawing-card/UI regressions; repository Ruff checks; full `.venv/bin/python -m pytest -q`.
- Result: `759 passed, 22 skipped` in 14.95s; Ruff clean. Coverage proves formula-free literal summary values, million-ruble scaling and legacy update, bundled-vs-local feedback precedence, every explicit review action replayed without manual review, and responsive second-row UI contract.
- Risks or follow-up: none within scope.

## Handoff

Leave this card in `review` until orchestration accepts the result.
