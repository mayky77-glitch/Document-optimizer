---
type: orda_task
status: frozen
card_id: reconciliation-real-data-source-core-v4
version: 1
supersedes: null
work_id: reconciliation-real-data-resilience-v4
task_id: reconciliation-real-data-source-core-v4
purpose: Build fail-soft per-workbook cumulative reconciliation extraction and deterministic global grouping.
role: developer
owner: reconciliation-real-data-source-developer
card_path: knowledge/tasks/reconciliation-real-data-source-core-v4.md
card_commit_sha_source: exact planning commit supplied by Gate 0 launch envelope
profile: L2
routing_grade: P4
routing_reason: Ambiguous multi-row workbook schemas and authoritative cumulative calculations require difficult cross-component implementation.
reasoning_effort: high
assigned_model: gpt-5.6-terra
launch_status: planned
planning_parent_sha: 9abfbc9e3773c1474b4caef21faf3164507d8fb9
base_sha_source: exact planning commit supplied by Gate 0 launch envelope
dependency_shas: []
branch: codex/reconciliation-real-data-source-core-v4
branch_base_source: exact planning commit supplied by Gate 0 launch envelope
write_scope:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/reconciliation_review/grouping.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/processing
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - tests
  - knowledge/maps
contract_versions:
  input: ReconciliationSourceDescriptor-1.0
  output: ReconciliationSourceBatch-1.0
acceptance_commands:
  - .venv/bin/ruff check src/report_processor/admin_panel/reconciliation_sources.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/reconciliation_review/grouping.py
  - .venv/bin/ruff format --check src/report_processor/admin_panel/reconciliation_sources.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/reconciliation_review/grouping.py
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
  - layer/backend
  - risk/high
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-resilience-v4-gate0|Gate 0]]"
---

# Reconciliation source core

## Frozen contract

- Define focused immutable source descriptor/result/issue models in
  `reconciliation_sources.py`. An issue exposes only a controlled code, safe basename,
  Russian comment, Russian repair hint and `can_continue`; never raw exceptions or
  workbook locations.
- Infer index/period only from safe upload metadata. Keep detection independent from
  the private filename.
- Inspect each workbook independently and select exactly one authoritative source:
  usable cumulative КС-6а first, otherwise КС-2 fallback. Reuse robust
  multi-row merged-header structural helpers without reading drawing-card remaining
  values as reconciliation period values.
- Return normalized rows with cumulative quantity and raw cost in the existing
  `period_quantity`/`period_cost` calculation boundary. Preserve `Decimal` values.
- Do not fail the batch for one bad source. If no source yields usable rows, raise a
  controlled all-sources-unusable error carrying only safe issues.
- Fix group ordering for empty units and group all exact/safe-prefix compatible rows
  completely and deterministically. Empty names stay singleton; broad fuzzy grouping
  is forbidden.
- Do not edit generic processing/calculation/writer engines or frontend/lifecycle
  files. Do not start the local service.

## Handoff evidence

Move to review only with changed paths, feature SHA, a diagnostic on the 12 immutable
private copies showing per-file usable row counts, no duplicated source contribution,
Ruff/format/diff-check output, risks and proposed merge order. Do not edit tests or
merge.

