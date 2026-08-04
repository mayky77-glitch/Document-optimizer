---
type: task
status: todo
card_status: frozen
version: 1
work_id: excel-pdf-reconciliation-wave10-v1
task_id: package-core
role: worker
agent_role: developer
owner: wave10-package-core
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: pending
source_base_sha: 967da5f58ee6508ebbfc3fc1d9fa2d7fe77dc0bb
branch: codex/wave10-excel-pdf-package-core
write_scope:
  - src/report_processor/package_reconciliation/__init__.py
  - src/report_processor/package_reconciliation/models.py
  - src/report_processor/package_reconciliation/discovery.py
  - src/report_processor/package_reconciliation/workbook.py
  - tests/unit/package_reconciliation/test_discovery.py
  - tests/unit/package_reconciliation/test_workbook.py
forbidden_paths:
  - src/report_processor/package_reconciliation/ocr.py
  - src/report_processor/package_reconciliation/pdf_documents.py
  - src/report_processor/cli.py
  - src/report_processor/admin_panel
  - "<private-corpus-root>"
  - "**/*.xlsx"
  - "**/*.pdf"
depends_on:
  - reconciliation-wave9-v1
contract_versions:
  output: PackageWorkbookFacts-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/package_reconciliation/test_discovery.py tests/unit/package_reconciliation/test_workbook.py
---

# Wave 10 package and workbook core

Implement immutable package/workbook DTOs, deterministic package discovery and
read-only KS-2 fact extraction. A package root is a directory containing one or
more `.xlsx`/`.xlsm` workbooks; related PDFs are collected recursively but not
through a nested package root. Preserve relative paths only. Reject symlinked
inputs and path escapes.

Discover headers structurally in the first 100 rows. Do not use fixed row or
column coordinates. Extract sheet act number/period, object code, position/work
code, drawing code, basis, work name, unit, quantity and total cost. Rows without
a stable work code or comparable work facts remain controlled issues. Open with
`read_only=True`, `data_only=True`, `keep_links=False`; always close; never save.
Tests must generate workbooks under `tmp_path` and must not add binary fixtures.
