---
type: orda_task
status: frozen
card_id: reconciliation-period-apply
version: 1
work_id: reconciliation-period-insertion-v1
task_id: period-apply
purpose: Use virtual future target cells for review and insert the period only after actionable calculations exist.
role: developer
route: P4 -> developer / gpt-5.6-terra / high; reason: cross-path review, calculation, writer and exact-replay identity integration.
launch_status: blocked-on-period-ooxml
card_path: knowledge/tasks/reconciliation-period-apply.md
card_commit_sha_source: exact period-insertion planning SHA supplied by launch envelope
base_sha_source: accepted period-ooxml integration SHA
branch: codex/reconciliation-period-apply
branch_base_sha_source: accepted period-ooxml integration SHA
write_scope:
  - src/report_processor/admin_panel/reconciliation_period.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_numeric_verification.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - tests/unit/admin_panel/test_reconciliation_period.py
  - tests/unit/admin_panel/test_reconciliation_target.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_verification.py
  - tests/integration/test_reconciliation_authoritative_flow.py
forbidden_paths:
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/calculation
  - src/report_processor/excel_writer/engine.py
  - src/report_processor/excel_writer/formula_materialization.py
  - knowledge
  - docs
contract_versions:
  input: ReconciliationPeriodInsertion-1.0+ReconciliationTargetMeasure-2.0
  output: ReconciliationTargetInsertionPreview-1.0+ReconciliationApplyIntegrity-3.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_period.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_period.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_period.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_period.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_period.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Period preview and apply integration

When strict target reading reports only `TARGET_CURRENT_PERIOD_PAIR_MISSING`, reconciliation with
an explicit period may build non-writable virtual target rows at the plan's future coordinates.
All work/index/unit/category facts remain from the immutable original target. Preview catalog,
package, target and apply identities include period plus plan digest so decisions from another
period or topology cannot replay.

Apply takes one immutable decision snapshot, rebuilds the preview and calculates normally. If no
calculated item contains a quantity or cost value, publish the original target byte-for-byte and do
not call the transformer. Otherwise prepare one private target, strict-read it, require its detected
pair/catalog/target IDs to equal the preview, rebuild matches and calculations from the same
decisions, and require a canonical semantic calculation digest match before invoking the existing
verified cell writer. The original target and source uploads remain unchanged.

`verify` continues to call only the strict reader; no planner, preview or transformer import may be
reachable from that operation. Missing/ambiguous/unsupported insertion remains a technical
no-artifact error. Prepared paths and plan details stay private. Owned temporary cleanup is
inode-safe; failed prepared copies are never served.

Regressions cover preview ID stability, changed period/plan replay rejection, restart snapshot
invalidation, zero-action byte identity/no temp, selected insert+reread+recalculate+write, semantic
drift rejection, source/target mutation, existing-pair idempotence, mixed-sheet failure, exact
technical codes and proof that verification never invokes insertion.
