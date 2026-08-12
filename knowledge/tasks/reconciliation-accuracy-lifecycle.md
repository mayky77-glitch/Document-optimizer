---
type: task
status: draft
card_id: reconciliation-accuracy-lifecycle
version: 1
work_id: reconciliation-max-accuracy-specialists-v1
task_id: production-lifecycle
purpose: Audit production reconciliation orchestration and job transaction boundaries.
role: worker
agent_role: debugger
owner: production-lifecycle
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
source_base_sha_source: exact planning commit supplied in launch envelope
branch: codex/reconciliation-accuracy-lifecycle
branch_base_sha_source: exact planning commit supplied in launch envelope
write_scope: []
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - "**/*.xlsx"
contract_versions:
  input: AdminReconciliationLifecycle-1.0
  output: ReconciliationLifecycleAudit-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_block18_admin_panel.py
tags:
  - task/review
  - status/draft
  - domain/document-processing
  - capability/admin-panel
  - risk/high
---

# Production lifecycle audit

Read-only audit of `/` upload, prepare, decision, apply, feedback and download ordering.
Prove unresolved or changed inputs fail closed, apply is one-shot/idempotent, verified output
precedes durable feedback, partial files are cleaned and active versus inert processing paths are
unambiguous. Return lifecycle sequences and deterministic failure/retry reproductions.
