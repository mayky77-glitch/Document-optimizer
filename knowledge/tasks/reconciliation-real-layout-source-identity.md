---
type: orda_task
status: accepted
card_id: reconciliation-real-layout-source-identity
version: 1
work_id: reconciliation-real-layout-v1
task_id: source-identity
purpose: Select one real cumulative source layout and terminal document identity from structural evidence without guessing.
role: developer
route: P4 -> developer / gpt-5.6-terra / high; reason: multi-file structural parser with private-XLSX counterexamples and consequential financial identity.
launch_status: completed
accepted_feature_sha: 1860741e5cf0bb9e38e01a55a1376a876c9c85b8
accepted_integration_sha: 3364bb387506a586343fc1a29bf46712ae13bd0a
published_main_sha: fe3d5eee01077c6130dd67b5f300d20fb316f276
card_path: knowledge/tasks/reconciliation-real-layout-source-identity.md
card_commit_sha_source: exact real-layout planning SHA supplied by launch envelope
base_sha_source: exact real-layout planning SHA
branch: codex/reconciliation-real-layout-source-identity
branch_base_sha_source: exact real-layout planning SHA
write_scope:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_identity.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_sources_layout.py
  - tests/unit/admin_panel/test_reconciliation_sources_provenance.py
  - tests/unit/admin_panel/test_reconciliation_target.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/integration/test_reconciliation_real_data.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_numeric_verification.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - knowledge
  - docs
contract_versions:
  input: UniversalReconciliationSource-2.0+ReconciliationTargetStage-2.0
  output: UniversalReconciliationSource-3.0+ReconciliationTerminalIdentity-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_sources_layout.py tests/unit/admin_panel/test_reconciliation_sources_provenance.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/integration/test_reconciliation_real_data.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_sources.py src/report_processor/admin_panel/reconciliation_identity.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_sources_layout.py tests/unit/admin_panel/test_reconciliation_sources_provenance.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/integration/test_reconciliation_real_data.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_sources.py src/report_processor/admin_panel/reconciliation_identity.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_sources_layout.py tests/unit/admin_panel/test_reconciliation_sources_provenance.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_reconciliation_execution.py tests/integration/test_reconciliation_real_data.py
  - git diff --check
---

# Structural source and terminal identity

Build an immutable header graph from actual merged spans and bounded nonempty header cells. Parent
labels propagate only through their merged horizontal scope. A viable layout binds one semantic work
column, one unit column and adjacent quantity/total-cost leaves under one cumulative or direct parent
region. Deduplicate candidates with the same physical columns/header boundary before ambiguity
evaluation. Broad stems may nominate roles, but may not rank a tied result by phrase or position.

Find the first detail row from non-header work text, a textual unit and finite/cache-verifiable metric
evidence; skip displayed numbering and footers. A formula in an eligible metric without a trustworthy
cache is a controlled source issue. Preserve exact source sheet/row provenance and permutation-stable
row IDs.

Create one shared terminal identity helper. Target values accept an unambiguous bare four-digit index
or final three/four-digit component of a full dotted identifier, preserving leading zeroes; years and
multiple candidates fail closed. Source basenames may yield a bounded primary plus parenthetical
candidate set. Resolve only one intersection with terminal identities present in the selected target
stage; zero/multiple intersections are controlled source issues.

This wave must not change the approved arithmetic or start target-column insertion. Keep current
downstream numeric compatibility, but carry explicit direct/cumulative measure provenance so the next
wave can remove positional/semantic aliasing deliberately. Do not add narrow normalization, unit
conversion, filename disclosure or a silent fallback.

## Acceptance

Accepted after `37 passed, 1` explicit private-data skip, Ruff/format/diff gates and independent
P6 merge review. The source reader binds metric leaves to the exact nominated merged parent,
structurally excludes work/unit candidates inside that metric scope and resolves bounded source
identities only through one selected-stage intersection.
