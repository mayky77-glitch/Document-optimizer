---
type: task
status: done
work_id: drawing-card-million-values-v3
role: worker
agent_role: developer
owner: "million-xlsx-developer"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: "xlsx-literal-million-values"
no_progress_count: 0
circuit_state: closed
routing_reason: "Proven XLSX output boundary with literal scaled values"
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
  - "src/report_processor/drawing_card/output/contract.py"
  - "src/report_processor/drawing_card/output/planner.py"
  - "src/report_processor/drawing_card/output/writer.py"
  - "src/report_processor/drawing_card/output/summary.py"
  - "src/report_processor/drawing_card/output/validator.py"
source_paths:
  - "src/report_processor/drawing_card/output/contract.py"
  - "src/report_processor/drawing_card/output/planner.py"
  - "src/report_processor/drawing_card/output/writer.py"
  - "src/report_processor/drawing_card/output/summary.py"
  - "src/report_processor/drawing_card/output/validator.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
  - "drawing-card"
  - "xlsx"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Стоимость в млн руб. и числовая сводка

## Goal

Keep internal costs in rubles while writing all workbook cost cells as literal million-ruble values with three decimals. The summary must contain no formulas and legacy update mode must preserve units.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `output/contract.py`, `output/planner.py`, `output/writer.py`, `output/summary.py`, `output/validator.py`.
- Commands and tests run: Ruff clean; focused summary/update regressions pass; full pytest `759 passed, 22 skipped`; `git diff --check`; real-workbook structural/value inspection.
- Result: main and summary headers declare million rubles; costs keep full precision as literal million-ruble numbers and display three decimals, so component sums do not drift. Summary has four styled cards and zero formulas. New cards convert displayed millions back to internal rubles on update; legacy ruble headers remain compatible. Real artifact: 403927 bytes; `0906` stores `7.809011` and displays `7.809`; all-index power cost stores `1073.67245176` and displays `1073.672`.
- Risks or follow-up: none within scope.

## Handoff

Leave this card in `review` until orchestration accepts the result.
