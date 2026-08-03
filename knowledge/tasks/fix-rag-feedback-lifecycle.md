---
type: task
status: done
work_id: drawing-card-contract-check-rag-v1
role: worker
agent_role: worker
owner: "rag-feedback-developer"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Localized confirmed lifecycle bug in exact review feedback persistence"
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
  - "src/report_processor/admin_panel/drawing_card_service.py"
source_paths:
  - "src/report_processor/admin_panel/drawing_card_service.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
  - "domain/drawing-card"
  - "capability/rag-feedback"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Сохранить initial review snapshot после ready rerun

## Goal

`apply_inline_review` must persist feedback from the reviewed rows and approvals
that existed before its non-strict rerun replaces job state.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `src/report_processor/admin_panel/drawing_card_service.py`
  - `knowledge/tasks/fix-rag-feedback-lifecycle.md`
- Commands and tests run:
  - `python3 -m py_compile src/report_processor/admin_panel/drawing_card_service.py`
  - `uv run ruff check src/report_processor/admin_panel/drawing_card_service.py`
  - `git diff --check`
- Result: passed. `apply_inline_review` copies `job.review_rows` and
  `job.inline_approvals` before `_run`; only a successful `ready` rerun calls
  `append_feedback` with those copies. Failed and blocked reruns still skip it.
- Risks or follow-up: shallow mapping snapshots rely on the existing immutable
  review-row and approval value objects; no user/workbook metadata is persisted.

## Handoff

Accepted: snapshot is captured before rerun; failed/blocked reruns do not write feedback.
