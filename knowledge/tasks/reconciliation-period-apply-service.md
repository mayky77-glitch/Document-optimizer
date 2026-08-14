---
type: orda_task
status: frozen
card_id: reconciliation-period-apply-service
version: 1
work_id: reconciliation-period-apply-v2
task_id: period-apply-service
purpose: Apply period preview through immutable calculation and restart-safe exact replay.
role: developer
route: P5 -> developer / gpt-5.6-terra / high; reason: transactional apply, manifest migration and crash recovery.
launch_status: blocked-on-period-preview
card_path: knowledge/tasks/reconciliation-period-apply-service.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: accepted period-preview integration SHA
branch: codex/reconciliation-period-apply-service
branch_base_sha_source: accepted period-preview integration SHA
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
  input: ReconciliationTargetInsertionPreview-1.0+ReconciliationTargetIdentity-1.0
  output: ReconciliationCalculationSemantics-1.0+ReconciliationApplyIntegrity-3.0+AdminReconciliationJobManifest-3.0+ReconciliationApplyReplay-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Period-aware apply and recovery

Add optional `reporting_period` to `AdminJob` and `create_job`, parse once with `ReportingPeriod`,
reject any non-null value for `verify`, and persist/recover canonical null/`YYYY-MM` in manifest v3.
Reconciliation uses a new period-aware review entry; verification continues calling the strict
existing `prepare_review()` and must not import or invoke planner, preview or transformer.

Catalog/package/target/state/apply identities consume `target_identity_digest`. Define the semantic
calculation digest as canonical JSON sorted by calculation ID with contract, calculation ID, target
row ID, status and writer-adapted quantity/cost exact Decimal strings or null. `apply_key` and
payload include target identity, period, plan and calculation digests.

Apply freezes decisions and immutable inputs, calculates against preview, and treats a calculated
zero as actionable while null/null is not. No actionable result publishes the original snapshot
byte-for-byte and never prepares a target. Otherwise transform one private target, strict-reread,
rebuild catalog/matches/calculations from the same snapshots/decisions/rules, require identical
catalog/target IDs and semantic digest, then invoke the existing verified writer.

Persist only bounded replay evidence before SQLite. Applying recovery validates inputs/output,
rebuilds period preview and calculation evidence without transformer/writer, requires exact digest
equality and exact-replays the feedback commit once. Invalid/missing/v2 evidence remains unavailable.

Regressions cover verify no-planner, period manifest round-trip/rejection, virtual review restart,
ID/digest changes, null/null byte identity/no temp, Decimal zero action, strict reread/recalculate,
semantic/catalog drift, input mutation, existing-pair idempotence, mixed/unsupported topology and
crashes before/after SQLite commit. API/routes/UI remain untouched; no private/full run.
