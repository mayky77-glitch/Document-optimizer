---
type: task
status: blocked
work_id: reconciliation-wave6a-remediation-v1
role: worker
agent_role: developer
owner: "wave6a-remediation"
profile: L2
routing_grade: P4
progress_revision: 3
state_fingerprint: ""
no_progress_count: 3
circuit_state: hard_stop
routing_reason: "P6 and security audits found authority, context, privacy and hard-negative bypasses"
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
  - "src/report_processor/reconciliation_patterns/hybrid_retrieval.py"
  - "tests/contract/test_hybrid_retrieval_contract.py"
  - "tests/unit/reconciliation_patterns/test_hybrid_retrieval.py"
source_paths:
  - "knowledge/tasks/reconciliation-wave6-contract.md"
depends_on:
  - "reconciliation-wave6-core"
  - "reconciliation-wave6-tests"
tags:
  - "task/remediation"
  - "status/blocked"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 6A audit remediation

Implement the recovered exact contract in one bounded production/test scope.
Required counterexamples: bare authority, raw path/URI, foreign context,
prototype lifecycle, every invalid channel matrix entry, missing source,
exact-only positive/negative, reverse directed edge, cross-representation margin,
noncanonical ranks/collections and cardinality bounds. Leave adapter queued.

Final follow-up: replace public authority factory with history resolver; make
all hybrid `auto_accepted` values false; split confirmed/prototype source IDs;
close outcome, canonical tuple, margin, direct result/ref and malformed-type
counterexamples from the second P6/security audit.

## Final audit result

REJECT after the last permitted remediation. Focused tests: `8 passed`; legacy
reconciliation-pattern and registry tests: `103 passed`; Ruff, format and
`py_compile` passed. Blocking counterexamples remain: callable `_build`,
noncanonical direct batch contents, two-negative result/explanation mismatch,
bool-as-int and result-bound bypasses, and raw `TypeError` for mixed refs.

ORDA hard stop is active. No adapter or runtime wiring may start from this core.
