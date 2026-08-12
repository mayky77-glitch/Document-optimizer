---
type: task
status: draft
card_id: reconciliation-accuracy-state
version: 1
work_id: reconciliation-max-accuracy-specialists-v1
task_id: decision-state
purpose: Audit decision precedence, replay, persistence and public payloads.
role: worker
agent_role: debugger
owner: decision-state
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
source_base_sha_source: exact planning commit supplied in launch envelope
branch: codex/reconciliation-accuracy-state
branch_base_sha_source: exact planning commit supplied in launch envelope
write_scope: []
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - "**/*.xlsx"
contract_versions:
  input: ReconciliationReviewState-1.0
  output: ReconciliationStateAudit-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/reconciliation_review/test_authoritative_core.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_batch_state.py tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/integration/test_reconciliation_batch_api.py tests/integration/test_reconciliation_review_ui_contract.py
tags:
  - task/review
  - status/draft
  - domain/document-processing
  - layer/backend
  - risk/high
---

# Decision state and replay audit

Read-only audit of package/family/group/row precedence, stale-version rejection, undo,
autosave/restart, feedback replacement and API redaction. Return an exact precedence table,
state-transition evidence, payload allowlist and tampered/stale request reproductions.
