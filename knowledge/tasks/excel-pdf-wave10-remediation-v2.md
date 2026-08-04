---
type: task
status: todo
card_status: frozen
version: 1
work_id: excel-pdf-reconciliation-wave10-remediation-v2
task_id: review-remediation
role: worker
agent_role: developer
owner: wave10-integration-cli
profile: L2
routing_grade: P4
branch: codex/wave10-excel-pdf-remediation-v2
write_scope:
  - src/report_processor/package_reconciliation/discovery.py
  - src/report_processor/package_reconciliation/matcher.py
  - src/report_processor/package_reconciliation/ocr.py
  - src/report_processor/package_reconciliation/pdf_documents.py
  - src/report_processor/package_reconciliation/pipeline.py
  - src/report_processor/cli_package_reconciliation.py
  - tests/unit/package_reconciliation/test_discovery.py
  - tests/unit/package_reconciliation/test_matcher.py
  - tests/unit/package_reconciliation/test_ocr.py
  - tests/unit/package_reconciliation/test_pdf_documents.py
  - tests/integration/test_package_reconciliation_cli.py
  - tests/integration/test_package_reconciliation_pipeline.py
  - tests/integration/test_package_reconciliation_real_data.py
forbidden_paths:
  - "<private-corpus-root>"
  - "**/*.xlsx"
  - "**/*.xlsm"
  - "**/*.xlsb"
  - "**/*.pdf"
  - src/report_processor/admin_panel
acceptance_commands:
  - uv run pytest -q tests/unit/package_reconciliation tests/integration/test_package_reconciliation_cli.py tests/integration/test_package_reconciliation_pipeline.py
  - uv run ruff check src/report_processor/package_reconciliation src/report_processor/cli_package_reconciliation.py tests/unit/package_reconciliation tests/integration/test_package_reconciliation_cli.py tests/integration/test_package_reconciliation_pipeline.py
  - uv run ruff format --check src/report_processor/package_reconciliation src/report_processor/cli_package_reconciliation.py tests/unit/package_reconciliation tests/integration/test_package_reconciliation_cli.py tests/integration/test_package_reconciliation_pipeline.py
---

# Wave 10 independent-review remediation

Close all eight MEDIUM findings from the independent read-only audit. Project
codes must be compared as structured delimiter-separated components: exact code
or a true component extension is allowed, while a last-component prefix is not.
Use the row's own drawing code first and inherit the nearest preceding parent
only when it is absent.

Treat a text layer as usable only when it contains sufficient structured AОСР
evidence; otherwise run the existing bounded local OCR. Exact-scope ОЖР or other
unsupported documents must produce `NEEDS_REVIEW` evidence without OCR, not
`NO_EVIDENCE`. Encountered symlink directories fail closed. A root without a
discoverable workbook package raises a controlled error and CLI exit code `2`.

The opt-in real pilot must perform discovery-only budget validation before any
OCR: at most two workbooks and six PDFs, then require non-empty safe results.
Do not run the opt-in test or inspect any private package in this task. All new
regressions are synthetic and must not reuse pilot paths, identifiers or values.
