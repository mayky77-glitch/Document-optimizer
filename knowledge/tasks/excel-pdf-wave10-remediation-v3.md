---
type: task
status: todo
card_status: frozen
version: 1
work_id: excel-pdf-reconciliation-wave10-remediation-v3
task_id: residual-remediation
role: worker
agent_role: developer
owner: wave10-integration-cli
profile: L2
routing_grade: P4
branch: codex/wave10-excel-pdf-remediation-v3
write_scope:
  - src/report_processor/package_reconciliation/matcher.py
  - src/report_processor/package_reconciliation/pipeline.py
  - src/report_processor/package_reconciliation/report.py
  - tests/unit/package_reconciliation/test_matcher.py
  - tests/unit/package_reconciliation/test_report.py
  - tests/integration/test_package_reconciliation_cli.py
  - tests/integration/test_package_reconciliation_pipeline.py
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

# Wave 10 residual remediation

This is the second and final implementation attempt for two residual findings.
For one exact-scope unsupported PDF, return `NEEDS_REVIEW` and preserve its safe
relative path. For multiple unsupported candidates, return `AMBIGUOUS` and
serialize a deterministic, validated tuple of candidate relative paths; never
OCR unsupported documents.

When discovery finds a workbook package but extraction yields no comparable
rows, raise a controlled `ValueError`; CLI must return `2` and must not create a
report. Cover both cases with synthetic fixtures only. Do not inspect or run any
private package.
