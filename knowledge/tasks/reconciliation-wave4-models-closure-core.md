---
type: task
status: done
work_id: reconciliation-wave4-models-closure-v1
role: worker
agent_role: developer
owner: "wave4-models-closure-core"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: "sha256:f84ef4c022dce2fc263026cf77fd0bcb9f8fdfd77f9fdcc72a2385ce51775b15"
no_progress_count: 0
circuit_state: closed
routing_reason: "P6 isolated approval loader and full-outcome graph contract defects"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: "gpt-5.6-terra"
actual_reasoning_effort: "high"
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "src/report_processor/reconciliation_patterns/pattern_models.py"
source_paths:
  - "src/report_processor/reconciliation_patterns/pattern_models.py"
depends_on:
  - "reconciliation-wave4-models-audit"
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 4 model contract closure

## Goal

Close approval provenance, strict proposal-container loading and full-outcome
feedback graph semantics.

## Scope and instructions

- Modify only `write_scope` paths.
- Preserve prior approval revision when a later revision becomes active.
- Require JSON arrays before converting every proposal/slot tuple.
- Bind full OutcomeSignature confirmations to typed endpoints and relation rules.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/reconciliation_patterns/pattern_models.py`
  and this closure card only.
- Commands and tests run: CodeGraph sync/query/explore; `.venv/bin/ruff
  format --check` and `.venv/bin/ruff check`; closure contract plus Wave 3
  profile/mine/evaluate/offline regression (`53 passed`); dedicated lifecycle,
  proposal-array and full-outcome graph create/canonical/load smoke.
- Result: real sequential lifecycle accepts retained owner approval from
  revision 3 in imported active revision 4 while activation metadata must match
  revision 4 and Wave 4 transition still fails `WAVE5_REQUIRED`. Proposal tuple
  fields require JSON arrays before conversion. Feedback endpoints and both
  confirmations carry full Wave 3 `OutcomeSignature`; edge validation binds the
  exact outcome multiset to endpoints, requires full equality for must-link and
  confirmed full conflict for cannot-link/hard-negative. Synthetic
  `hard_boundary` outcomes are rejected.
- Risks or follow-up: persistence remains responsible for verifying that each
  previous fingerprint points to the actual prior row; this module validates
  revision-local provenance and all canonical payloads.

## Handoff

Leave this card in `review` until orchestration accepts the result.
