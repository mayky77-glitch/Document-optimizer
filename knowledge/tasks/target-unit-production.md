---
type: task
status: draft
work_id: review-target-unit-v1
role: worker
agent_role: developer
owner: "developer-1"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Cross API UI session contract using active workflow category units"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
write_scope:
  - "src/report_processor/admin_panel/drawing_card_service.py"
  - "src/report_processor/admin_panel/drawing_card_presentation.py"
  - "src/report_processor/admin_panel/app.py"
  - "src/report_processor/admin_panel/assets/drawing-card.js"
  - "src/report_processor/admin_panel/assets/drawing-card.html"
source_paths:
  - "src/report_processor/admin_panel/drawing_card_service.py"
  - "src/report_processor/admin_panel/drawing_card_presentation.py"
  - "src/report_processor/admin_panel/app.py"
  - "src/report_processor/admin_panel/assets/drawing-card.js"
  - "src/report_processor/admin_panel/assets/drawing-card.html"
depends_on: []
tags:
  - "task/implementation"
  - "status/draft"
  - "admin"
  - "review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Update review target units with category selection

## Goal

Define the concrete outcome before moving this card to `claimed`.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
