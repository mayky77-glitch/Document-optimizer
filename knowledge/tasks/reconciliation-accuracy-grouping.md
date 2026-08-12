---
type: task
status: draft
card_id: reconciliation-accuracy-grouping
version: 1
work_id: reconciliation-max-accuracy-specialists-v1
task_id: grouping-safety
purpose: Audit global group, family and package membership and mass-safe boundaries.
role: worker
agent_role: debugger
owner: grouping-safety
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
source_base_sha_source: exact planning commit supplied in launch envelope
branch: codex/reconciliation-accuracy-grouping
branch_base_sha_source: exact planning commit supplied in launch envelope
write_scope: []
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - "**/*.xlsx"
contract_versions:
  input: ReconciliationGrouping-2.0
  output: ReconciliationGroupingAudit-1.0
acceptance_commands:
  - uv run pytest -q tests/contract/test_reconciliation_grouping_contract.py tests/unit/reconciliation_grouping
tags:
  - task/review
  - status/draft
  - domain/document-processing
  - layer/backend
  - risk/high
---

# Grouping and package safety audit

Read-only audit of visible-row partitioning and deterministic group/family/package construction.
Prove exact-once membership, permutation invariance, zero-activity isolation and fail-closed
handling of unit, category, hard-conflict and incomplete-pair cases. Return a membership ledger,
boundary matrix and minimal reproduction for every unsafe or unstable result.
