---
type: orda_task
status: frozen
card_id: reconciliation-period-preview-complete
version: 1
work_id: reconciliation-period-apply-v4
task_id: period-preview-complete
purpose: Complete structural period preview with bounded shared header discovery and a coherent writable schema.
role: developer
route: P5 -> developer / gpt-5.6-terra / high; reason: cross-layer XLSX parsing, immutable identity and verified OOXML planning.
launch_status: planned
card_path: knowledge/tasks/reconciliation-period-preview-complete.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: exact planning commit containing this card
branch: codex/reconciliation-period-preview-complete
branch_base_sha_source: exact planning commit containing this card
checkpoint_sha: 88bb4562f67ab4baac5eae95494c98970f54e0b7
write_scope:
  - src/report_processor/admin_panel/reconciliation_period_preview.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_target_measure.py
  - src/report_processor/excel_writer/period_insertion.py
  - tests/unit/admin_panel/test_reconciliation_period_preview.py
  - tests/unit/admin_panel/test_reconciliation_state.py
  - tests/unit/admin_panel/test_reconciliation_target.py
  - tests/unit/admin_panel/test_reconciliation_target_measure.py
  - tests/unit/excel_writer/test_period_insertion.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_numeric_verification.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/assets
  - knowledge
  - docs
contract_versions:
  input: ReconciliationPeriodInsertion-1.1+ReconciliationTargetMeasure-2.0
  output: ReconciliationTargetSelection-1.0+ReconciliationTargetInsertionPreview-1.0+ReconciliationTargetIdentity-1.0+BoundedHeaderWindow-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_period.py tests/unit/admin_panel/test_reconciliation_period_preview.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_period_preview.py src/report_processor/admin_panel/reconciliation_state.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_target_measure.py src/report_processor/excel_writer/period_insertion.py tests/unit/admin_panel/test_reconciliation_period_preview.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_period_preview.py src/report_processor/admin_panel/reconciliation_state.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_target_measure.py src/report_processor/excel_writer/period_insertion.py tests/unit/admin_panel/test_reconciliation_period_preview.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/excel_writer/test_period_insertion.py
  - git diff --check
---

# Complete structural period preview

Integrate checkpoint `88bb4562f67ab4baac5eae95494c98970f54e0b7` by merge, not cherry-pick or
rebase. It contains dynamic base-role binding, immutable period identity, request-local physical
cell snapshots, coherent reconciliation-owned schemas and the current-pair bounded path. Preserve
its six-file behavior while closing the shared historical-planner gap below.

Replace rectangular header discovery driven by worksheet `max_column` with one explicit bounded
header-window contract. For each selected sheet the caller supplies or derives the exact rows above
the first semantic detail row. Candidate columns come only from physically materialized cells in
that window and merged ranges intersecting it. An unrelated far-row/far-column cell, including
`XFD999999`, must not enlarge work. Duplicate, malformed, over-limit or contradictory evidence
fails closed. Do not add fixed target columns, month phrases, private-template exceptions or a
narrow alias list.

The public current reader, historical preview, insertion-plan builder and transformer preflight
must consume the same bounded discovery semantics. Generated end-to-end regressions cover shifted
multilevel headers, an irrelevant far cell, both current and missing-current preview paths, exact
one-pass workbook snapshots, coherent schema worksheets/status/diagnostics/period/cardinality, and
writer identity acceptance. Source bytes remain unchanged and no output may be published on any
preflight failure.

This task supersedes the blocked frozen `reconciliation-period-apply-v2/period-preview` scope; the
blocked runtime evidence remains historical and must not be rewritten.
