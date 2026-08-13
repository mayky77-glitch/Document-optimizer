---
type: orda_task
status: frozen
card_id: admin-verification-apply-integrity
version: 1
work_id: admin-verification-lifecycle-v1
task_id: apply-integrity
purpose: Make authoritative reconciliation apply exact-once and feedback/output publication transactional.
role: developer
card_path: knowledge/tasks/admin-verification-apply-integrity.md
card_commit_sha_source: exact lifecycle planning SHA supplied by launch envelope
base_sha_source: lifecycle planning SHA
branch: codex/admin-verification-apply-integrity
branch_base_sha_source: lifecycle planning SHA
write_scope:
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_feedback_store.py
  - src/report_processor/admin_panel/service.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_feedback_store.py
  - tests/integration/test_reconciliation_authoritative_flow.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - knowledge
  - docs
contract_versions:
  input: VerificationNumericOracle-2.0+SafeGrouping-2.0
  output: ReconciliationApplyIntegrity-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_feedback_store.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_feedback_store.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Apply integrity

Build one stable apply plan from the job ID, immutable input digests, stage, validated rules hash,
state fingerprint and canonical effective decisions. Use the same loaded rules object for the write.

Before calculation, reserve every accepted physical source identity exactly once across all target
buckets. Do not normalize sheet names or introduce unit conversion. `_catalog` must reject a second
eligible `(terminal index, category_id)` and `prepare_review` must expose this as a controlled target
error.

Publish and validate the owned job-local output, set mode `0600`, capture identity and SHA-256, then
commit feedback through an idempotent SQLite `apply_key`. Exact replay adds no rows; a same-key
payload conflict fails closed. The feedback rows and apply marker commit in one `BEGIN IMMEDIATE`
transaction. No fallible output operation follows the database commit. Before a proven rollback,
cleanup may remove only the inode owned by this attempt; a concurrent replacement survives.

Keep legacy feedback readable and do not delete/rebuild an unknown database schema.
