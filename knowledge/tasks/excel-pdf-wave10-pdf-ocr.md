---
type: task
status: todo
card_status: frozen
version: 1
work_id: excel-pdf-reconciliation-wave10-v1
task_id: pdf-ocr
role: worker
agent_role: developer
owner: wave10-pdf-ocr
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: pending
source_base_sha: 967da5f58ee6508ebbfc3fc1d9fa2d7fe77dc0bb
branch: codex/wave10-excel-pdf-ocr
write_scope:
  - src/report_processor/package_reconciliation/ocr.py
  - src/report_processor/package_reconciliation/pdf_documents.py
  - tests/unit/package_reconciliation/test_ocr.py
  - tests/unit/package_reconciliation/test_pdf_documents.py
forbidden_paths:
  - src/report_processor/package_reconciliation/__init__.py
  - src/report_processor/package_reconciliation/models.py
  - src/report_processor/package_reconciliation/discovery.py
  - src/report_processor/package_reconciliation/workbook.py
  - src/report_processor/cli.py
  - src/report_processor/admin_panel
  - "<private-corpus-root>"
  - "**/*.xlsx"
  - "**/*.pdf"
depends_on:
  - reconciliation-wave9-v1
contract_versions:
  output: PackagePdfEvidence-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/package_reconciliation/test_ocr.py tests/unit/package_reconciliation/test_pdf_documents.py
---

# Wave 10 local PDF OCR

Implement bounded local adapters for `pdfinfo`, `pdftotext`, `pdftoppm` and
Tesseract `rus+eng`. Use argument arrays, timeouts, temporary directories and
controlled error codes; never use shell interpolation. Prefer a usable text
layer, otherwise render selected pages at 300 DPI and parse Tesseract TSV into
text, mean confidence and token bounding boxes. Do not persist OCR text.

Classify AОСР, ОЖР, АКТ and other documents from normalized basenames. Extract
controlled AОСР fields from pages 1–2: act number/date, project or drawing codes,
work-description section and explicit quantity/unit candidates. Basename alone
may narrow candidates but never proves a match. Tests mock the command runner or
use text fixtures only; no real or synthetic binary PDF may be committed.
