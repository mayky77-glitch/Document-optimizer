---
type: orda_task
status: frozen
card_id: admin-verification-remediation-target-writer
version: 1
work_id: admin-verification-remediation-v2
task_id: target-writer
purpose: Make adjacent reconcile target type policy and post-publication cleanup ownership-safe.
role: developer
card_path: knowledge/tasks/admin-verification-remediation-target-writer.md
card_commit_sha_source: exact planning SHA supplied by launch envelope
base_sha_source: accepted Wave 1 integration SHA supplied by launch envelope
dependency_shas_source: accepted source-target feature SHA
branch: codex/admin-verification-target-writer
branch_base_sha_source: accepted Wave 1 integration SHA
write_scope:
  - src/report_processor/excel_writer/engine.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - tests/unit/excel_writer/test_engine.py
  - tests/unit/admin_panel/test_reconciliation_target.py
  - tests/integration/test_block15_excel_writer.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/reconciliation_grouping
  - knowledge
  - docs
contract_versions:
  input: TargetWriter-1.0
  output: TargetWriterSafety-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/excel_writer/test_engine.py tests/unit/admin_panel/test_reconciliation_target.py tests/integration/test_block15_excel_writer.py
  - uv run --extra dev ruff check src/report_processor/excel_writer/engine.py src/report_processor/admin_panel/reconciliation_target.py tests/unit/excel_writer/test_engine.py tests/unit/admin_panel/test_reconciliation_target.py tests/integration/test_block15_excel_writer.py
  - uv run --extra dev ruff format --check src/report_processor/excel_writer/engine.py src/report_processor/admin_panel/reconciliation_target.py tests/unit/excel_writer/test_engine.py tests/unit/admin_panel/test_reconciliation_target.py tests/integration/test_block15_excel_writer.py
  - git diff --check
---

# Adjacent target writer safety

After publishing, cleanup may unlink output only when it still owns the published inode/token;
another actor's replacement must survive reopen failure. Define one target `.xlsm` policy across
selected and no-selected reconciliation paths. Until the writer can preserve VBA, package type and
signatures through calculation materialization, reject target `.xlsm` before review with a
controlled Russian input error; source `.xlsm` verification annotation remains supported. Add
replacement-race and selected/no-selected target-type regressions.
