---
type: orda_task
status: frozen
card_id: reconciliation-period-ooxml
version: 1
work_id: reconciliation-period-insertion-v1
task_id: period-ooxml
purpose: Plan and verify one direct OOXML insertion of a reporting-period quantity/cost pair.
role: developer
route: P4 -> developer / gpt-5.6-terra / high; reason: exact package transformation with formulas and coordinate-bearing workbook structures.
launch_status: planned
card_path: knowledge/tasks/reconciliation-period-ooxml.md
card_commit_sha_source: exact period-insertion planning SHA supplied by launch envelope
base_sha_source: exact period-insertion planning SHA
branch: codex/reconciliation-period-ooxml
branch_base_sha_source: exact period-insertion planning SHA
write_scope:
  - src/report_processor/admin_panel/reconciliation_target_measure.py
  - src/report_processor/admin_panel/reconciliation_period.py
  - src/report_processor/excel_writer/period_insertion.py
  - src/report_processor/excel_writer/__init__.py
  - tests/unit/admin_panel/test_reconciliation_period.py
  - tests/unit/excel_writer/test_period_insertion.py
  - tests/unit/admin_panel/test_reconciliation_target_measure.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_verification.py
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
  input: ReconciliationTargetMeasure-2.0
  output: ReconciliationPeriodInsertion-1.0+ReconciliationPeriodInsertionDelta-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_period.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_target_measure.py src/report_processor/admin_panel/reconciliation_period.py src/report_processor/excel_writer/period_insertion.py src/report_processor/excel_writer/__init__.py tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_period.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_target_measure.py src/report_processor/admin_panel/reconciliation_period.py src/report_processor/excel_writer/period_insertion.py src/report_processor/excel_writer/__init__.py tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_period.py tests/unit/excel_writer/test_period_insertion.py
  - git diff --check
---

# Direct OOXML period insertion

Add immutable `ReportingPeriod`, sheet anchor, insertion plan and prepared-target results. Validate
only exact zero-padded `YYYY-MM`. Discover one historical/documentary adjacent quantity/total-cost
pair per selected-stage sheet using the accepted merged-header graph; require real suffix content,
reject unit price, missing/tied anchors and mixed current/missing sheet state. The insertion boundary
is immediately after the historical cost column. Existing current pair is an idempotent no-plan;
explicit parseable conflict fails.

Create two unmerged columns directly in OOXML. Add identical full month+year identity to broad
quantity and total-cost leaf labels. Clone widths and each row's style IDs from the historical pair,
but never copy values, formulas, comments or hyperlinks. Use inline strings so styles and shared
strings stay byte-identical.

Preflight and translate one exact two-column insertion rule across cell coordinates, dimensions,
row spans, column definitions, non-crossing merges, simple local A1 formula operands, calcChain,
conditional-format ranges with non-reference rule bodies, auto-filter ranges/filter IDs, simple
print area/titles and supported drawing anchors. Expand a range containing the boundary; shift a
range wholly to its right; preserve a range wholly left. Reject formula names/external/structured
references, `INDIRECT`/`ADDRESS`, shared/array/dynamic formulas, crossing merges, affected comments,
tables, validations, charts, external links, pivots, slicers, OLE/controls, extension lists and any
unknown affected coordinate-bearing structure.

Write to one owned private temp, preserve ZIP entry order/comment/metadata, fsync, and publish
no-clobber. An independent verifier derives changed parts from the frozen plan, proves every
unaffected entry byte-identical, applies inverse coordinate mapping to all pre-existing structures,
validates inserted blank/style/header nodes, checks source digest again, reopens the result and
requires the accepted detector to find exactly the planned pair. Failure removes only the owned
temporary identity and exposes one controlled code without paths, sheets, coordinates or values.

Regressions cover varied columns/header depth/multisheet boundaries; missing/tied/unit-price/mixed
anchors; exact period validation and conflict/idempotence; every supported coordinate structure;
every rejected feature family; ZIP preservation; source/output races; no-clobber cleanup; inverse
delta tampering; and strict detector reread. Tests use only generated minimal workbooks/packages.
