---
type: orda_task
status: frozen
card_id: admin-verification-remediation-artifact
version: 1
work_id: admin-verification-remediation-v2
task_id: artifact
purpose: Make red-row OOXML styles and multi-workbook verification publication byte-safe and no-clobber.
role: developer
card_path: knowledge/tasks/admin-verification-remediation-artifact.md
card_commit_sha_source: exact planning SHA supplied by launch envelope
base_sha_source: same exact planning SHA
dependency_shas: []
branch: codex/admin-verification-artifact
branch_base_sha_source: same exact planning SHA
write_scope:
  - src/report_processor/excel_writer/row_annotations.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - tests/unit/excel_writer/test_row_annotations.py
  - tests/unit/admin_panel/test_reconciliation_verification.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/reconciliation_grouping
  - knowledge
  - docs
contract_versions:
  input: VerificationArtifact-1.0
  output: VerificationArtifact-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/excel_writer/test_row_annotations.py tests/unit/admin_panel/test_reconciliation_verification.py
  - uv run --extra dev ruff check src/report_processor/excel_writer/row_annotations.py src/report_processor/admin_panel/reconciliation_verification.py tests/unit/excel_writer/test_row_annotations.py tests/unit/admin_panel/test_reconciliation_verification.py
  - uv run --extra dev ruff format --check src/report_processor/excel_writer/row_annotations.py src/report_processor/admin_panel/reconciliation_verification.py tests/unit/excel_writer/test_row_annotations.py tests/unit/admin_panel/test_reconciliation_verification.py
  - git diff --check
---

# Verification artifact integrity

Replace regex-based `<xf>` child extraction with a quote-aware byte-slice scanner that preserves
unrelated XML bytes and handles adjacent self-closing/paired children. Keep source digest, VBA and
all unchanged package entries intact; signed packages remain rejected by existing policy.

For multi-source output, create unique private temp annotations and a unique temp ZIP in the job
directory, verify it, then use `publish_no_clobber`. Cleanup only temp paths created by this call.
Never delete an existing final artifact or a legacy deterministic temp name after failure. Preserve
stable member names/order, result size limit, mode `0600` and same-suffix XLSM annotation.
