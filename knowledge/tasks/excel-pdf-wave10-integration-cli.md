---
type: task
status: todo
card_status: frozen
version: 1
work_id: excel-pdf-reconciliation-wave10-v1
task_id: integration-cli
role: worker
agent_role: developer
owner: wave10-integration-cli
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: pending
source_base_sha: 715d2bccf92020886357533220ef7466c32b9b27
branch: codex/wave10-excel-pdf-integration-cli
write_scope:
  - src/report_processor/package_reconciliation/__init__.py
  - src/report_processor/package_reconciliation/matcher.py
  - src/report_processor/package_reconciliation/pipeline.py
  - src/report_processor/package_reconciliation/report.py
  - src/report_processor/cli_package_reconciliation.py
  - src/report_processor/cli.py
  - tests/unit/package_reconciliation/test_matcher.py
  - tests/unit/package_reconciliation/test_report.py
  - tests/integration/test_package_reconciliation_pipeline.py
  - tests/integration/test_package_reconciliation_cli.py
  - tests/integration/test_package_reconciliation_real_data.py
forbidden_paths:
  - src/report_processor/package_reconciliation/ocr.py
  - src/report_processor/package_reconciliation/pdf_documents.py
  - src/report_processor/package_reconciliation/models.py
  - src/report_processor/package_reconciliation/discovery.py
  - src/report_processor/package_reconciliation/workbook.py
  - src/report_processor/admin_panel
  - "<private-corpus-root>"
  - "**/*.xlsx"
  - "**/*.pdf"
depends_on:
  - package-core
  - pdf-ocr
contract_versions:
  input_workbook: PackageWorkbookFacts-1.0
  input_pdf: PackagePdfEvidence-1.0
  output: ExcelPdfReconciliation-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/package_reconciliation tests/integration/test_package_reconciliation_pipeline.py tests/integration/test_package_reconciliation_cli.py
---

# Wave 10 reconciliation pipeline and CLI

Implement `report-processor reconcile-package --package <dir> --output <json>`.
Discover package roots, extract workbook rows, narrow PDF candidates by exact
normalized work-code parent directory, then OCR only relevant AОСР candidates.
Never process every PDF merely because it is present. ОЖР and unsupported types
remain filename/context evidence and require review unless explicitly supported.

Automatic evidence requires exact work-code scope plus at least one independent
content signal: project-code backbone or work-description similarity. Basename
alone is never sufficient. Compare quantity only when the PDF exposes one
explicit section-1 quantity/unit pair and units are compatible; support common
length conversion between `м` and `км`. Cost remains `NOT_COMPARABLE` unless the
PDF explicitly contains a scoped cost fact. Multiple equally strong candidates,
low OCR confidence, missing tools or missing content return `AMBIGUOUS` or
`NEEDS_REVIEW`, never a guessed match.

Output contract statuses: `MATCH`, `MISMATCH`, `AMBIGUOUS`, `NO_EVIDENCE`,
`NEEDS_REVIEW`. Default canonical JSON may contain controlled relative paths,
sheet/row references, normalized comparison values, confidence and reason codes;
it must never contain absolute paths, raw OCR text, formulas or subprocess errors.
Write atomically with mode `0600`. Unit/integration tests generate workbooks at
runtime and stub OCR. Real-data test is opt-in via environment variable and may
use only the two designated small pilot packages; all other packages stay
reserved for later holdout.
