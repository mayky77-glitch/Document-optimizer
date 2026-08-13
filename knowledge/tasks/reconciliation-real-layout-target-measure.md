---
type: orda_task
status: accepted
card_id: reconciliation-real-layout-target-measure
version: 1
work_id: reconciliation-target-measure-v1
task_id: target-measure
purpose: Discover the current-period target quantity/cost pair from structural header evidence and remove positional J/K verification.
role: developer
route: P4 -> developer / gpt-5.6-terra / high; reason: cross-path numeric correctness and fail-closed target interpretation.
launch_status: completed
accepted_feature_sha: 57a56efa7621e3d65277e6117e033a6718094f1f
accepted_integration_sha: 1362c538bbb81fdb5d16e5617cd4f9a55cb01632
published_main_sha: 959e3b94bca5c441b56a12f3bb22d371c79567de
card_path: knowledge/tasks/reconciliation-real-layout-target-measure.md
card_commit_sha_source: exact planning commit supplied by launch envelope
base_sha_source: exact planning commit
branch: codex/reconciliation-target-measure
branch_base_sha_source: exact planning commit
write_scope:
  - src/report_processor/admin_panel/reconciliation_target_measure.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_numeric_verification.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/service.py
  - tests/unit/admin_panel/test_reconciliation_target_measure.py
  - tests/unit/admin_panel/test_reconciliation_target.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_verification.py
  - tests/unit/admin_panel/test_reconciliation_job_recovery.py
  - tests/integration/test_reconciliation_authoritative_flow.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_identity.py
  - src/report_processor/schema
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/assets
  - knowledge
  - docs
contract_versions:
  input: ReconciliationTargetMeasure-1.0+UniversalReconciliationSource-3.0
  output: ReconciliationTargetMeasure-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_target_measure.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_target_measure.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Structural target measure

Add one reconciliation-local immutable detector. For each worksheet that contributes semantic rows
to the selected stage, inspect only the bounded header band above its first detail row. Propagate
labels through real merged ranges. Nominate adjacent quantity then total-cost leaves broadly; reject
unit-price leaves and any pair with cumulative, documentary or historical conflict evidence.

A candidate needs positive current-period evidence. It may be supplied by one coherent merged
parent/path or by the same single parseable calendar-period identity in both adjacent leaf paths.
Mere location, a generic word `period`, numeric data or a partial phrase cannot qualify. Physically
identical repeated evidence deduplicates; zero candidates raises
`TARGET_CURRENT_PERIOD_PAIR_MISSING`, and multiple distinct candidates raise
`TARGET_CURRENT_PERIOD_PAIR_AMBIGUOUS`. Legacy J/K is eligible only if it passes this same contract;
there is no positional fallback, ranking or private-template exception.

`read_reconciliation_target()` keeps its public return type. Its schema bindings and every
`TargetReportRow` cell snapshot come from the sheet-local discovered pair, retaining coordinate,
raw lexeme, formula/cache state, style and status. The writer already resolves logical bindings to
exact coordinates and remains unchanged. Bump row/catalog/apply-plan and recovery manifest
contract identities so obsolete J/K verdicts cannot replay as current-period evidence.

`prepare_review()` preserves the exact private target-measure error code. Verification maps it to a
technical failure before annotations or output publication; missing/ambiguous pair therefore has no
passed verdict, red workbook or ZIP. Existing trusted-cache and exact-unit rules stay unchanged.
Reconcile also stops before review/apply until a later wave explicitly inserts a valid pair.

Regressions cover: historical pair plus a later unmerged common-month pair; historical-only missing;
structurally valid legacy pair; same-parent adjacency; split/conflicting parents; unit price;
duplicate evidence; two candidate periods; alternate wording; sheet-local columns; formula/cache
provenance; numeric verdict independence from contradictory historical cells; discovered-cell-only
apply; no-artifact failure; and invalidation of obsolete manifests/apply identities.

## Acceptance

Accepted after `104 passed`, Ruff/format/diff gates and independent P6 review. The final detector
rejects multi-period and mixed month/month+year evidence before any current-parent fallback, while
preserving broad total-cost wording and exact technical error propagation.
