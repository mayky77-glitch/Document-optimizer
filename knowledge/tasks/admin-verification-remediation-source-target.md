---
type: orda_task
status: frozen
card_id: admin-verification-remediation-source-target
version: 1
work_id: admin-verification-remediation-v2
task_id: source-target
purpose: Make source layout, formula cache, document index, duplicate upload and target-stage discovery fail closed and universal.
role: developer
card_path: knowledge/tasks/admin-verification-remediation-source-target.md
card_commit_sha_source: exact planning SHA supplied by launch envelope
base_sha_source: same exact planning SHA
dependency_shas: []
branch: codex/admin-verification-source-target
branch_base_sha_source: same exact planning SHA
write_scope:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_uploads.py
  - tests/unit/admin_panel/test_reconciliation_sources_provenance.py
  - tests/unit/admin_panel/test_reconciliation_target.py
  - tests/unit/admin_panel/test_service.py
  - tests/integration/test_reconciliation_real_data.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/reconciliation_grouping
  - src/report_processor/excel_writer
  - knowledge
  - docs
contract_versions:
  input: ReconciliationSourceBatch-1.0
  output: UniversalReconciliationSource-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_sources_provenance.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_real_data.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_sources.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_uploads.py tests/unit/admin_panel/test_reconciliation_sources_provenance.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_real_data.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_sources.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_uploads.py tests/unit/admin_panel/test_reconciliation_sources_provenance.py tests/unit/admin_panel/test_reconciliation_target.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_real_data.py
  - git diff --check
---

# Source and target safety

Implement RA-001/002/003/011/016 and reusable stage-discovery primitives. Header discovery must
merge variable-depth hierarchical paths and select one coherent structural candidate; do not add a
closed phrase allowlist. Cumulative evidence outranks a generic direct pair only when internally
valid. Equal candidates fail controlled ambiguity. Determine first data row from semantic detail
evidence, retaining the first valid row and skipping number/header rows.

Read formula and cached-value projections together. A formula in an otherwise eligible metric cell
without a finite cached value produces a controlled source issue; it is never silently dropped.
Use canonical document-index extraction and reject ambiguous/year-only identities. Reject duplicate
source SHA before job storage. Add target stage enumeration/resolution primitives: one valid stage can
auto-select; zero/multiple return typed controlled outcomes; explicit missing stage fails. Do not wire
UI/service behavior in this card.
