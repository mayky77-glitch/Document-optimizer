---
type: orda_task
status: frozen
card_id: reconciliation-period-ui
version: 1
work_id: reconciliation-period-ui-v1
task_id: period-ui
purpose: Expose optional exact reporting period for reconciliation without weakening verification.
role: developer
route: P5 -> developer / inherited runtime; reason: API contract, operation-aware UI state and retry behavior.
launch_status: blocked-on-reconciliation-writer-namespace-v3
card_path: knowledge/tasks/reconciliation-period-ui.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: accepted reconciliation-writer-namespace-v3 integration SHA
branch: codex/reconciliation-period-ui
branch_base_sha_source: accepted reconciliation-writer-namespace-v3 integration SHA
write_scope:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/assets/index.html
  - src/report_processor/admin_panel/assets/admin.js
  - tests/integration/test_block18_admin_panel.py
  - tests/unit/admin_panel/test_presentation.py
  - tests/integration/test_verification_ui_contract.py
forbidden_paths:
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_period_preview.py
  - src/report_processor/excel_writer
  - src/report_processor/calculation
  - knowledge
  - docs
contract_versions:
  input: AdminReconciliationJobManifest-3.0+ReconciliationTargetIdentity-1.0
  output: AdminReconciliationPeriodUI-1.0
acceptance_commands:
  - nice -n 10 uv run --extra dev pytest -q tests/integration/test_block18_admin_panel.py tests/unit/admin_panel/test_presentation.py tests/integration/test_verification_ui_contract.py tests/integration/test_reconciliation_authoritative_flow.py
  - nice -n 10 uv run --extra dev ruff check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/presentation.py tests/integration/test_block18_admin_panel.py tests/unit/admin_panel/test_presentation.py tests/integration/test_verification_ui_contract.py
  - nice -n 10 uv run --extra dev ruff format --check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/presentation.py tests/integration/test_block18_admin_panel.py tests/unit/admin_panel/test_presentation.py tests/integration/test_verification_ui_contract.py
  - git diff --check
---

# Reconciliation reporting-period API and UI

The service already owns exact `YYYY-MM` parsing, persistence, restart identity and the controlled
rejection of any period for `verify`. This wave exposes that accepted contract without adding
normalization in HTTP or JavaScript.

Raise the bounded form-field count from three to four, read `reporting_period` exactly as submitted
and pass it to `create_job` in every upload path. Do not trim, case-fold or reinterpret it. A crafted
verification request with any nonempty period must return the existing controlled 400 before job
creation. Reconciliation without a period remains the current physical-pair path.

Every reconciliation presentation, including authoritative manual review, exposes only
`operation: "reconcile"` and canonical `reporting_period: YYYY-MM | null`. Verification exposes
`operation: "verify"` and no period field. Preserve current payload privacy: no paths, digests,
sheet names, coordinates, formulas or stage-discovery evidence.

Replace the fixed hidden verification operation with an explicit operation control and a native
month input. The month control is visible/enabled and serialized only for reconciliation. Switching
to verification clears and disables it so stale state cannot be submitted. A stage-selection 409
retry preserves source files, target file, exact operation and exact period without inventing a
period or normalizing stage labels. Verification rendering remains selected only by the server's
`payload.operation`.

Generated tests cover reconcile with `2026-08`, omitted period, strict whitespace rejection,
crafted verify+period with zero service calls, selection-required retry, safe payload fields and
static UI behavior for clear/disable/serialization. Keep all existing accessibility labels and
keyboard-native controls.
