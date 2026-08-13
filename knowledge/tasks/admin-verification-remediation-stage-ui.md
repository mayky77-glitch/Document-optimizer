---
type: orda_task
status: frozen
card_id: admin-verification-remediation-stage-ui
version: 1
work_id: admin-verification-remediation-v2
task_id: stage-ui
purpose: Remove hidden stage 13.1 and add automatic single-stage or explicit multi-stage selection to API and UI.
role: developer
card_path: knowledge/tasks/admin-verification-remediation-stage-ui.md
card_commit_sha_source: exact planning SHA supplied by launch envelope
base_sha_source: accepted Wave 1 integration SHA supplied by launch envelope
dependency_shas_source: accepted source-target feature SHA
branch: codex/admin-verification-stage-ui
branch_base_sha_source: accepted Wave 1 integration SHA
write_scope:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/models.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/assets/index.html
  - src/report_processor/admin_panel/assets/admin.js
  - tests/unit/admin_panel/test_service.py
  - tests/unit/admin_panel/test_presentation.py
  - tests/integration/test_block18_admin_panel.py
  - tests/integration/test_reconciliation_review_ui_contract.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/excel_writer
  - src/report_processor/reconciliation_grouping
  - knowledge
  - docs
contract_versions:
  input: TargetStageSelection-2.0
  output: AdminStageSelection-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_presentation.py tests/integration/test_block18_admin_panel.py tests/integration/test_reconciliation_review_ui_contract.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/service.py src/report_processor/admin_panel/models.py src/report_processor/admin_panel/presentation.py tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_presentation.py tests/integration/test_block18_admin_panel.py tests/integration/test_reconciliation_review_ui_contract.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/service.py src/report_processor/admin_panel/models.py src/report_processor/admin_panel/presentation.py tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_presentation.py tests/integration/test_block18_admin_panel.py tests/integration/test_reconciliation_review_ui_contract.py
  - node --check src/report_processor/admin_panel/assets/admin.js
  - git diff --check
---

# Target stage API and UI

Omitted stage means automatic discovery, never `13.1`. Exactly one valid stage is selected and
reported safely. Zero fails with a Russian repair action and no artifact. Multiple stages return
safe options and require an explicit choice; UI adds one compact selector only in that state and
resubmits the same immutable uploads through an established safe flow. Explicit missing stage
fails before review/verdict. Keep public payload free of paths, sheets and cell coordinates.
