---
type: task
status: done
work_id: reconciliation-wave4-conflict-contract-recovery-v1
role: auditor
agent_role: architect
owner: "wave4-conflict-contract-recovery"
profile: L3
routing_grade: P6
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: open
routing_reason: "Accepted endpoint binding makes persisted must-vs-negative contradiction unconstructable"
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: confirmed
actual_model: "gpt-5.6-sol"
actual_reasoning_effort: "high"
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope: []
source_paths:
  - "src/report_processor/reconciliation_patterns/pattern_models.py"
  - "src/report_processor/reconciliation_patterns/feedback_graph.py"
  - "src/report_processor/reconciliation_patterns/pattern_persistence.py"
depends_on:
  - "reconciliation-wave4-persistence-remediation"
tags:
  - "task/audit"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 4 conflict contract recovery

## Goal

Choose the smallest fail-closed contract correction that makes authoritative
must-vs-negative contradictions persistable without weakening provenance,
identity, privacy, activation or scope isolation.

## Required output

- Prove the collision with concrete valid model states.
- Compare minimal compatible correction options.
- Freeze exact symbols, tests and compatibility risks for one recovery cycle.
- Do not edit code.

## Completion evidence

- Changed paths: this orchestration card only.
- Result: collision proven. `PatternRecord.expected_outcome` is proposal output;
  `FeedbackEndpoint.outcome` is authoritative observed output. Remove only the
  cross-model equality checks from `validate_explicit_edge`; retain exact
  pattern/candidate identity, full scope, confirmation-outcome multiset,
  relation/reason and provenance validation. No payload/version/schema change.
- Risks or follow-up: add graph and persistence regressions for must-vs-negative
  contradictions, owner-approved fail-closed, active suspension, atomic rollback
  and insertion-order independence before accepting Wave 4.
