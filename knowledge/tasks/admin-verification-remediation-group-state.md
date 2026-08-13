---
type: orda_task
status: frozen
card_id: admin-verification-remediation-group-state
version: 1
work_id: admin-verification-remediation-v2
task_id: group-state
purpose: Prevent unsafe mixed-unit mass decisions, dangling feedback constraints and non-atomic restart restoration.
role: developer
card_path: knowledge/tasks/admin-verification-remediation-group-state.md
card_commit_sha_source: exact planning SHA supplied by launch envelope
base_sha_source: same exact planning SHA
dependency_shas: []
branch: codex/admin-verification-group-state
branch_base_sha_source: same exact planning SHA
write_scope:
  - src/report_processor/reconciliation_grouping/features.py
  - src/report_processor/reconciliation_grouping/packages.py
  - src/report_processor/reconciliation_grouping/constraints.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_batch_store.py
  - tests/unit/reconciliation_grouping/test_features_and_partition.py
  - tests/unit/reconciliation_grouping/test_packages.py
  - tests/unit/admin_panel/test_reconciliation_state.py
  - tests/unit/admin_panel/test_reconciliation_batch_state.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/excel_writer
  - knowledge
  - docs
contract_versions:
  input: ReconciliationPackageBatch-2.0
  output: SafeGrouping-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/reconciliation_grouping/test_features_and_partition.py tests/unit/reconciliation_grouping/test_packages.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_batch_state.py
  - uv run --extra dev ruff check src/report_processor/reconciliation_grouping/features.py src/report_processor/reconciliation_grouping/packages.py src/report_processor/reconciliation_grouping/constraints.py src/report_processor/admin_panel/reconciliation_state.py src/report_processor/admin_panel/reconciliation_batch_store.py tests/unit/reconciliation_grouping/test_features_and_partition.py tests/unit/reconciliation_grouping/test_packages.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_batch_state.py
  - uv run --extra dev ruff format --check src/report_processor/reconciliation_grouping/features.py src/report_processor/reconciliation_grouping/packages.py src/report_processor/reconciliation_grouping/constraints.py src/report_processor/admin_panel/reconciliation_state.py src/report_processor/admin_panel/reconciliation_batch_store.py tests/unit/reconciliation_grouping/test_features_and_partition.py tests/unit/reconciliation_grouping/test_packages.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_batch_state.py
  - git diff --check
---

# Grouping and restart state safety

A package may be `safe` for `quantity_cost` only when every member has the same non-empty exact
normalized unit and that unit is recognized. Same-family but different exact units (`м`/`км`) and
UNKNOWN units require manual review; no automatic conversion. Cost-only behavior remains explicit.
Reject or surface any negative constraint whose endpoint does not exist after group materialization.

Restore package/family/group/row decision snapshots atomically from a prospective complete state;
do not validate version hashes against a partially restored map or leave partial mutations after a
stale snapshot. Add multi-scope restart, rollback, permutation and unit regressions.
