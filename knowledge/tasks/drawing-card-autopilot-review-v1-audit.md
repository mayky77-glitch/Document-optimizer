---
type: task
card_id: drawing-card-autopilot-review-v1-audit
status: draft
version: 1
work_id: drawing-card-autopilot-review-v1
task_id: audit
purpose: "Проверить финансовую безопасность review autopilot"
role: auditor
agent_role: reviewer
owner: "reviewer"
profile: L3
routing_grade: P6
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Consequential financial-category auto-resolution final review"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/drawing-card-autopilot-review-v1-audit.md
base_sha_ref: accepted_integration_sha
write_scope: []
source_paths: []
depends_on: []
tags:
  - "task/audit"
  - "status/draft"
  - "drawing-card"
  - "review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Drawing card review autopilot audit

## Goal

Audit fail-closed guards, provenance, exact scoping, aggregate invariants and rollback.

## Scope and instructions

- Audit read-only.
- Reject any quantity auto-include across unit mismatch.
- Reject any dependency on RuBERT category/score for activation.
- Require private replay residual actions <= 25 and unchanged aggregate/card totals.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
