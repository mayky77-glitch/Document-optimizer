---
type: orda_task
status: frozen
card_id: admin-verification-job-recovery
version: 1
work_id: admin-verification-lifecycle-v1
task_id: job-recovery
purpose: Restore safe review and ready jobs after service restart and in-memory pruning.
role: developer
card_path: knowledge/tasks/admin-verification-job-recovery.md
card_commit_sha_source: exact lifecycle planning SHA supplied by launch envelope
base_sha_source: accepted apply-integrity integration SHA supplied by launch envelope
dependency_shas_source: accepted apply-integrity feature SHA
branch: codex/admin-verification-job-recovery
branch_base_sha_source: accepted apply-integrity integration SHA
write_scope:
  - src/report_processor/admin_panel/drawing_card_job_store.py
  - src/report_processor/admin_panel/service.py
  - tests/unit/admin_panel/test_drawing_card_job_store.py
  - tests/unit/admin_panel/test_reconciliation_job_recovery.py
  - tests/unit/admin_panel/test_service.py
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
  input: ReconciliationApplyIntegrity-1.0
  output: AdminReconciliationJobManifest-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_drawing_card_job_store.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/drawing_card_job_store.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_drawing_card_job_store.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/drawing_card_job_store.py src/report_processor/admin_panel/service.py tests/unit/admin_panel/test_drawing_card_job_store.py tests/unit/admin_panel/test_reconciliation_job_recovery.py tests/unit/admin_panel/test_service.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Restart and pruning recovery

Parameterize the existing hardened private manifest store by expected contract without changing its
drawing-card default. Persist only bounded job metadata, safe names, SHA-256 values and normalized
job-relative paths. Never persist workbook cell values, formulas, sheet/row coordinates or absolute
paths.

`ready` restores only after input and output digest, regular-file, symlink and job-boundary checks;
a passed verification may legitimately have no output. `review_required` is reconstructed from
immutable uploads via `prepare_review`, which restores the existing atomic decision snapshot.
Interrupted pending/running work never reruns implicitly. An `applying` record may finish only by
revalidating the durable output and exact-replaying the idempotent apply commit; otherwise it fails
closed without duplicate feedback.

Memory pruning removes only the in-memory object. `get_job` may bounded-lazy-load the valid manifest
and artifact. Corrupt, hostile, oversized, stale or digest-mismatched manifests cannot make a result
downloadable and cannot block recovery of other jobs.
