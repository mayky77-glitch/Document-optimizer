---
type: task
status: blocked
work_id: reconciliation-wave2-v1
role: worker
agent_role: developer
owner: "wave2-core"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L1 compatibility profile maps to P3."
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
  - "src/report_processor/work_semantics/typed_slots.py"
  - "src/report_processor/work_semantics/semantic_skeleton.py"
source_paths:
  - "src/report_processor/work_semantics/typed_slots.py"
  - "src/report_processor/work_semantics/semantic_skeleton.py"
depends_on:
  - "reconciliation-wave2-contract"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 2 typed slots and semantic skeleton core

## Goal

Implement the accepted immutable `TypedSlots-1.0` and
`SemanticSkeleton-1.0` contracts in two isolated modules.

## Scope and instructions

- Modify only `write_scope` paths.
- Follow `reconciliation-wave2-contract` exactly: Decimal-only values, audit
  code-point spans, deterministic overlap precedence, stable warnings/conflicts,
  explicit-only text properties and document index removal from skeleton.
- No legacy integration, no `__init__.py` re-export, no Git operations.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: assigned typed-slots and semantic-skeleton modules only.
- Commands and tests run: Wave 2 focused 31 passed; Ruff/format/diff-check passed.
- Result: frozen parser/value/span/precedence/conflict/masking contract implemented.
- Risks or follow-up: isolated direct imports only; no legacy integration.

## Handoff

Superseded by `reconciliation-wave2-remediation-core` after final audit.
