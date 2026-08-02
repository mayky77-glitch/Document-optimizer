---
type: task
status: draft
orda_status: frozen
card_id: reconciliation-global-batch-review-v5-lifecycle
version: 1
work_id: reconciliation-global-batch-review-v5
task_id: lifecycle
purpose: Integrate package decisions into authoritative state, API, autosave, calculation and verified XLSX.
role: worker
agent_role: developer
owner: reconciliation-v5-lifecycle
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: Consequential precedence, stale-state, autosave, calculation and verified XLSX integration.
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
card_path: knowledge/tasks/reconciliation-global-batch-review-v5-lifecycle.md
card_commit_sha_ref: launch_envelope
base_sha_ref: wave1_integration_sha
dependency_shas_ref:
  - wave1_integration_sha
branch: codex/reconciliation-v5-lifecycle
branch_base_sha_ref: wave1_integration_sha
write_scope:
  - src/report_processor/admin_panel/reconciliation_batch_state.py
  - src/report_processor/admin_panel/reconciliation_batch_store.py
  - src/report_processor/admin_panel/reconciliation_batch_presentation.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_review_api.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/reconciliation_feedback_store.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/presentation.py
  - tests/unit/admin_panel/test_reconciliation_batch_state.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_feedback_store.py
  - tests/integration/test_reconciliation_authoritative_flow.py
  - tests/integration/test_reconciliation_batch_api.py
source_paths:
  - src/report_processor/reconciliation_grouping
  - src/report_processor/admin_panel/reconciliation_batch_state.py
  - src/report_processor/admin_panel/reconciliation_batch_store.py
  - src/report_processor/admin_panel/reconciliation_batch_presentation.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_review_api.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/reconciliation_feedback_store.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/presentation.py
  - tests/unit/admin_panel/test_reconciliation_batch_state.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_feedback_store.py
  - tests/integration/test_reconciliation_authoritative_flow.py
  - tests/integration/test_reconciliation_batch_api.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/reconciliation_grouping
  - src/report_processor/stage_rag
  - tests/fixtures
  - pyproject.toml
  - uv.lock
contract_versions:
  input: ReconciliationPackageContract-1.0
  output: ReconciliationBatchDecision-1.0
  autosave: ReconciliationBatchAutosave-1.0
  payload: ReconciliationBatchPayload-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/admin_panel/test_reconciliation_batch_state.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_reconciliation_batch_api.py tests/integration/test_reconciliation_real_data.py
  - uv run ruff check src/report_processor/admin_panel/reconciliation_batch_*.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_state.py src/report_processor/admin_panel/reconciliation_review_api.py src/report_processor/admin_panel/reconciliation_review_routes.py src/report_processor/admin_panel/reconciliation_feedback_store.py src/report_processor/admin_panel/service.py src/report_processor/admin_panel/presentation.py tests/unit/admin_panel/test_reconciliation_batch_state.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_reconciliation_batch_api.py
  - git diff --check
last_verified: 2026-08-02
updated: 2026-08-02
tags:
  - task/implementation
  - status/draft
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[reconciliation-global-batch-review-v5-core]]"
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Reconciliation global batch review v5 lifecycle

## Frozen contract

- Build packages only from non-zero review rows. Preserve hidden zero rows in the
  private source batch and create no decision or feedback for them.
- Store package, family, group and row decisions separately. Effective priority is
  row, group, family, package. Resolve once into existing group/row decisions before
  `apply_overrides`; do not create a second calculation path.
- Package/family decision category must be available for every affected row.
  Reject stale versions before mutation. Mass accept is restricted to safe packages.
- Autosave job-local decisions with the complete version fingerprint; restore only
  compatible state. Undo restores the previous decision snapshot without reread.
- Persist reusable feedback only after verified authoritative apply. Ready-result
  replay remains idempotent.
- Public payload uses opaque IDs and short Russian labels/reasons. Exclude paths,
  sheets, formulas, coordinates, digests, provenance, evidence, prompts, raw
  warnings, confidence and internal rule IDs.
- Keep `service.py` from growing; new lifecycle logic belongs in batch modules.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until ORDA accepts feature and merge SHAs.

