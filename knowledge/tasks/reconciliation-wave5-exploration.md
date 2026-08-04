---
type: task
status: done
work_id: reconciliation-wave5-contract-exploration-v1
role: worker
agent_role: explorer
owner: "wave5-exploration"
profile: L0
routing_grade: P2
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Map authoritative calculation, grouping, XLSX and holdout test seams before implementation"
assigned_model: gpt-5.6-terra
reasoning_effort: low
launch_status: inherited
actual_model: "gpt-5.6-terra"
actual_reasoning_effort: "medium"
fallback_reason: "Explorer inherited Terra/medium, a stronger runtime route than requested P2."
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope: []
source_paths: []
depends_on:
  - "reconciliation-wave4-final-acceptance"
tags:
  - "task/exploration"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 5 code and test exploration

## Goal

Map minimal isolated files, reusable authoritative oracles, fixtures and risks.

## Completion evidence

- Changed paths: none.
- Result: minimal isolated scope is `replay.py` plus contract/unit/integration
  tests. Test adapters may reuse `execute_reconciliation(write=None)`,
  `build_review_groups`, `build_reconciliation_packages` and
  `calculate_matches`; production replay imports none of them.
- Risks or follow-up: `write_target_report` writes/publishes XLSX and is excluded.
  `CorpusRecord.document_set_id` is the independent split key. Equivalence uses
  exact in-memory authoritative decisions/Decimals and injected XLSX oracle.
