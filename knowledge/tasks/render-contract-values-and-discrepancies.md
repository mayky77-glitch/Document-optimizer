---
type: task
status: done
work_id: drawing-card-contract-check-rag-v1
role: worker
agent_role: worker
owner: "contract-output-developer"
profile: L1
routing_grade: P3
progress_revision: 4
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded drawing-card aggregation, XLSX layout, validation, and discrepancy output"
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
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/aggregation/aggregator.py"
  - "src/report_processor/drawing_card/output"
  - "src/report_processor/drawing_card/contract_check.py"
source_paths:
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/aggregation/aggregator.py"
  - "src/report_processor/drawing_card/output"
  - "src/report_processor/drawing_card/contract_check.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Добавить договорные поля и лист расхождений

## Goal

Add contract and performed values to the existing card rows, then publish a
discrepancy registry only when the performed cost exceeds the contract cost by
more than 1,000 RUB.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `src/report_processor/drawing_card/models.py`
  - `src/report_processor/drawing_card/aggregation/aggregator.py`
  - `src/report_processor/drawing_card/contract_check.py`
  - `src/report_processor/drawing_card/output/{contract,layout,planner,writer,validator,discrepancies}.py`
- Commands and tests run:
  - `python3 -m compileall -q src/report_processor/drawing_card` — passed.
  - `.venv/bin/ruff check src/report_processor/drawing_card/models.py src/report_processor/drawing_card/aggregation/aggregator.py src/report_processor/drawing_card/contract_check.py src/report_processor/drawing_card/output` — passed.
  - `.venv/bin/pytest -q tests/unit/drawing_card/test_summary_report.py tests/unit/drawing_card/test_hierarchy_aggregates.py tests/unit/drawing_card/test_inline_review_flow.py tests/unit/admin_panel/test_drawing_card_service.py` — 38 passed.
- Result:
  - Quantity aggregates use the existing quantity source-row selection; cost aggregates use the existing cost source-row selection.
  - All four values remain `Decimal` in RUB until XLSX publication in million RUB.
  - Violations use the strict `> Decimal(1000)` rule; only the contract-cost cell is filled red, and an optional internally linked discrepancy sheet is created.
  - Write-operation provenance now covers each new metric using its corresponding existing source-row and matching provenance.
  - Template normalization clears both legacy six-column and new ten-column card slots within the managed card rows before rendering, preventing stale sample labels in spacer columns without touching user data outside the card region.
  - Reruns clear only the managed red contract-cost discrepancy fill before current violations are applied; the discrepancy registry's four values and cost difference are all included in exact Decimal XML rewriting.
- Risks or follow-up:
  - None in the owned production scope.

## Handoff

Accepted: output, tolerance, targeted red fill, hyperlink registry and stale-red clearing verified.
