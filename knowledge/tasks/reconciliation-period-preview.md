---
type: orda_task
status: frozen
card_id: reconciliation-period-preview
version: 1
work_id: reconciliation-period-apply-v2
task_id: period-preview
purpose: Build structural historical-target preview and period-bound immutable identity.
role: developer
route: P4 -> developer / gpt-5.6-terra / high; reason: structural XLSX selection and stable cross-layer identity.
launch_status: planned
card_path: knowledge/tasks/reconciliation-period-preview.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: exact planning commit containing this card
branch: codex/reconciliation-period-preview
branch_base_sha_source: exact planning commit containing this card
write_scope:
  - src/report_processor/admin_panel/reconciliation_period_preview.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - tests/unit/admin_panel/test_reconciliation_period_preview.py
  - tests/unit/admin_panel/test_reconciliation_target.py
  - tests/unit/admin_panel/test_reconciliation_state.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_numeric_verification.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/excel_writer
  - knowledge
  - docs
contract_versions:
  input: ReconciliationPeriodInsertion-1.1+ReconciliationTargetMeasure-2.0
  output: ReconciliationTargetSelection-1.0+ReconciliationTargetInsertionPreview-1.0+ReconciliationTargetIdentity-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_period.py tests/unit/admin_panel/test_reconciliation_period_preview.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_period_preview.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_state.py tests/unit/admin_panel/test_reconciliation_period_preview.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_state.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_period_preview.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_state.py tests/unit/admin_panel/test_reconciliation_period_preview.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_state.py
  - git diff --check
---

# Structural period preview

Resolve base target roles `DOCUMENT_INDEX`, `STAGE`, `ROW_NUMBER`, `WORK_NAME`, `UNIT` from the
existing logical schema and hierarchical header evidence. Require one unambiguous `OK` binding per
role, propagate index/stage values and select only semantic detail rows in the requested stage.
Never fall back to A–F, a private coordinate, phrase list or positional tie-break.

Keep `read_reconciliation_target()` strict: it requires one physical current-period pair and never
imports planner/transformer. Add `preview_reconciliation_target()` in a new module. For an exact
missing-pair result plus explicit `ReportingPeriod`, build the source-bound insertion plan and
project target rows with non-writable blank snapshots at each anchor's future
`cost_column + 1/+2`; work/index/unit/category facts remain from the immutable target.

Create `ReconciliationTargetIdentity` as canonical SHA-256 over contract, original target digest,
selected stage, nullable period and nullable plan digest. Add immutable `target_identity_digest` to
review state and its version fingerprint. Same inputs rebuild byte-identically; changed period,
plan or target changes every downstream identity. Existing physical pair uses period/plan null and
remains strict/idempotent.

Regressions cover shifted base columns, hierarchical headers, propagated index/stage, missing/tied
roles, historical preview, exact virtual coordinates/writable false, multisheet plan mapping,
identity determinism/change, original byte preservation and state fingerprint binding. Tests use
only generated workbooks; no service, verification, private corpus or full suite.
