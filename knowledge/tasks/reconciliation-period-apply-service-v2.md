---
type: orda_task
status: frozen
card_id: reconciliation-period-apply-service-v2
version: 1
work_id: reconciliation-period-apply-v4
task_id: period-apply-service
purpose: Apply the accepted period preview through immutable calculation and restart-safe exact replay.
role: developer
route: P5 -> developer / gpt-5.6-terra / high; reason: transactional apply, manifest migration and crash recovery.
launch_status: blocked-on-period-preview-complete
card_path: knowledge/tasks/reconciliation-period-apply-service-v2.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: accepted period-preview-complete integration SHA
branch: codex/reconciliation-period-apply-service-v2
branch_base_sha_source: accepted period-preview-complete integration SHA
write_scope:
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_numeric_verification.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/service.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_verification.py
  - tests/unit/admin_panel/test_reconciliation_job_recovery.py
  - tests/unit/admin_panel/test_service.py
  - tests/integration/test_reconciliation_authoritative_flow.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_period_preview.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_target_measure.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/excel_writer
  - src/report_processor/calculation
  - knowledge
  - docs
contract_versions:
  input: ReconciliationTargetInsertionPreview-1.0+ReconciliationTargetIdentity-1.0+BoundedHeaderWindow-1.0
  output: ReconciliationCalculationSemantics-1.0+ReconciliationApplyIntegrity-3.0+AdminReconciliationJobManifest-3.0+ReconciliationApplyReplay-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Period-aware apply and recovery v2

This card replaces the unlaunched v2 service card after the preview scope was superseded. Add an
optional canonical `reporting_period` to reconciliation jobs and manifest v3; reject any period for
`verify`. Verification remains strict and must neither import nor call preview, planner or
transformer.

Catalog, package, target, state and apply identities consume the accepted target identity. Freeze
decisions and immutable inputs, calculate against preview, and treat a calculated zero as
actionable while `null/null` is not. No actionable result publishes the original snapshot
byte-for-byte without preparing a target. An actionable historical result prepares one private
target, strict-rereads it, recalculates from the same snapshots/decisions/rules and requires equal
catalog, target and canonical writer-adapted calculation digests before the existing writer runs.

Persist only bounded replay evidence before SQLite. Applying recovery validates inputs/output,
rebuilds preview and calculation evidence without transformer/writer, requires exact equality and
exact-replays feedback once. Missing, malformed or legacy-v2 evidence remains unavailable. API,
routes and UI remain a later wave.
