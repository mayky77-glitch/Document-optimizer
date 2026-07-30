---
type: task
status: done
work_id: confirmed-fixes-20260730
role: worker
agent_role: worker
owner: "developer-workflow-remediation"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L2 compatibility profile maps to P4."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: "gpt-5.6-terra"
actual_reasoning_effort: "high"
fallback_reason: "Inherited developer runtime; requested P4 route was retained."
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
write_scope:
  - "src/report_processor/drawing_card/workflow.py"
  - "src/report_processor/drawing_card/review/io.py"
  - "src/report_processor/cli.py"
  - "src/report_processor/terminal_ui.py"
  - "tests/integration/test_workflow.py"
  - "tests/integration/test_review_flow.py"
  - "tests/unit/test_manual_review.py"
source_paths:
  - "src/report_processor/drawing_card/workflow.py"
  - "src/report_processor/drawing_card/review/io.py"
  - "src/report_processor/cli.py"
  - "src/report_processor/terminal_ui.py"
  - "tests/integration/test_workflow.py"
  - "tests/integration/test_review_flow.py"
  - "tests/unit/test_manual_review.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Workflow strict review and collision remediation

## Goal

Repair strict review-decision import and pre-publication workflow safeguards.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/drawing_card/workflow.py`,
  `src/report_processor/drawing_card/review/io.py`, `src/report_processor/cli.py`,
  `tests/integration/test_workflow.py`, `tests/integration/test_review_flow.py`,
  `tests/unit/test_manual_review.py`, and this card.
- Commands and tests run: scoped `ruff check` and `ruff format --check` (passed);
  focused pytest (24 passed); full pytest (56 passed); global `ruff check .`
  (passed). Global `ruff format --check .` is blocked only by the out-of-scope
  Markdown fence formatting in `docs/ТЗ_универсальная_CLI_карточка.md`.
- Result: `apply-drawing-review` emits a strictly validated JSON contract that
  `--review-decisions` imports, while XLSX review input remains supported.
  Invalid JSON review categories produce a controlled `BLOCKED` result with
  `error.json` and `processing_summary.json`. Strict publication centrally blocks
  `INVALID_NUMBER`, `EXCEL_ERROR`, `DRAWING_CODE_NOT_FOUND`, and prior blockers;
  audit artifacts still complete and no XLSX is published. Output collisions with
  the resolved template or existing card are blocked before manifest inspection.
- Risks or follow-up: The workspace has no `.git` metadata, so a commit/push was
  not possible and none was initialized. The global Ruff format check remains
  blocked by the unrelated documentation file noted above.

## Handoff

Leave this card in `review` until orchestration accepts the result.
