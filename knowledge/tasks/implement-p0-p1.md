---
type: task
status: draft
work_id: reconciliation-implementation-2026-07-28
role: auditor
agent_role: orchestrator
owner: "project-orchestrator"
profile: L3
routing_grade: P7
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Explicit owner request for very-high project orchestration; high-risk spreadsheet arithmetic and archive ingestion"
luna_benchmark_evidence: ""
exception_evidence: "sha256:8cd61c5153197888656cdd90071a11455c2e849216b2745a753a6d7471e1f14c"
assigned_model: gpt-5.6-sol
reasoning_effort: xhigh
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-28
updated: 2026-07-28
write_scope: []
source_paths: []
depends_on: []
tags:
  - "task/audit"
  - "status/draft"
  - "work/implementation"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[../components/document-reconciliation]]"
---

# Implement P0 and P1 foundation

## Goal

Define the concrete outcome before moving this card to `claimed`.

## Scope and instructions

- Audit read-only.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
