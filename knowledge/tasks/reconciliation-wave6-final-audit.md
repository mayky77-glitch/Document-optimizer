---
type: task
status: done
work_id: reconciliation-wave6-final-audit-v1
role: auditor
agent_role: reviewer
owner: "wave6-final-audit"
profile: L3
routing_grade: P6
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Authority and negative-evidence failures can alter reconciliation decisions"
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
  - "src/report_processor/reconciliation_patterns/hybrid_retrieval.py"
  - "tests/contract/test_hybrid_retrieval_contract.py"
  - "tests/unit/reconciliation_patterns/test_hybrid_retrieval.py"
depends_on:
  - "reconciliation-wave6a-remediation-v1"
tags:
  - "task/audit"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 6 final audit

## Result

REJECT. The normal focused suite passes (`8 passed`) and scoped Ruff is clean,
but adversarial construction still breaks the frozen contract.

## Blocking evidence

1. `AuthorityEnvelope._build` remains callable outside `resolve_authority` and
   can seal an unvalidated outcome.
2. Direct `SignalBatch` and `HardNegativeBatch` construction accepts reversed,
   noncanonical content and produces order-dependent fingerprints.
3. Two same-representation blockers make ranking fail because explanation and
   result bind different hard-negative reference sets.
4. Direct candidates accept bool-as-int; direct authoritative results accept
   source artifacts; direct results exceed `MAX_LIMIT`.
5. Mixed-type ref/code tuples can leak raw `TypeError` instead of a stable,
   privacy-safe `HybridRetrievalError`.

## Gate

Wave 6 core/tests are blocked. The adapter and all runtime wiring stay queued.
A new evidence revision must begin with executable counterexamples for all five
items, followed by one bounded implementation and a fresh P6 audit.
