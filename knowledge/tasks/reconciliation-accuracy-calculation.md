---
type: task
status: draft
card_id: reconciliation-accuracy-calculation
version: 1
work_id: reconciliation-max-accuracy-specialists-v1
task_id: matching-calculation
purpose: Audit authoritative matching and Decimal calculation semantics.
role: worker
agent_role: debugger
owner: matching-calculation
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
source_base_sha_source: exact planning commit supplied in launch envelope
branch: codex/reconciliation-accuracy-calculation
branch_base_sha_source: exact planning commit supplied in launch envelope
write_scope: []
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - "**/*.xlsx"
contract_versions:
  input: AuthoritativeReviewSelection-1.0
  output: ReconciliationCalculationAudit-1.0
acceptance_commands:
  - uv run pytest -q tests/contract/test_block12_matching_contract.py tests/integration/test_block12_matching_engine.py tests/contract/test_block13_calculation_contract.py tests/integration/test_block13_calculation_engine.py tests/integration/test_block13_authoritative_multi_selection.py
tags:
  - task/review
  - status/draft
  - domain/document-processing
  - layer/backend
  - risk/high
---

# Matching and Decimal calculation audit

Read-only audit from authoritative selected rows through matching and calculation. Prove every
accepted row contributes exactly once to its intended target with correct `quantity_cost` and
`cost_only` flags, compatible units, finite Decimal handling, coefficients and round-after-sum
behavior. Return a candidate-to-contribution trace and deterministic adversarial reproductions.
