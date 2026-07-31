---
type: task
status: draft
work_id: review-target-unit-v1
role: worker
agent_role: tester
owner: "tester-1"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded HTTP and browser asset regressions"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
write_scope:
  - "tests/integration/test_drawing_card_admin.py"
  - "tests/unit/admin_panel/test_drawing_card_service.py"
source_paths:
  - "tests/integration/test_drawing_card_admin.py"
  - "tests/unit/admin_panel/test_drawing_card_service.py"
depends_on:
  - "target-unit-production"
tags:
  - "task/implementation"
  - "status/draft"
  - "tests"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Test reactive target unit and accepted category

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
