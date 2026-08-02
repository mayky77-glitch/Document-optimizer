---
type: orda_task
status: frozen
card_id: reconciliation-real-data-remediation-v4
version: 1
work_id: reconciliation-real-data-remediation-v4
task_id: reconciliation-real-data-remediation-v4
purpose: Fix the focused KS-2 header boundary and legitimate all-reject authoritative output.
role: developer
owner: reconciliation-real-data-remediation-developer
card_path: knowledge/tasks/reconciliation-real-data-remediation-v4.md
card_commit_sha_source: exact remediation planning commit supplied by the launch envelope
profile: L1
routing_grade: P3
routing_reason: Two localized production defects with independent failing acceptance tests.
reasoning_effort: medium
assigned_model: gpt-5.6-terra
launch_status: planned
planning_parent_sha: 321e988a016629f3d093b47431b03872bb775702
base_sha_source: exact remediation planning commit supplied by the launch envelope
dependency_shas:
  - e0eba998137c2b7da9794ad0ffeba9ad5b4d0053
branch: codex/reconciliation-real-data-remediation-v4
write_scope:
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_target.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - tests
  - knowledge/maps
contract_versions:
  input: ReconciliationRealDataAcceptance-1.0
  output: ReconciliationRemediation-1.0
acceptance_commands:
  - .venv/bin/ruff check src/report_processor/admin_panel/reconciliation_sources.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_target.py
  - .venv/bin/ruff format --check src/report_processor/admin_panel/reconciliation_sources.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_target.py
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
  - risk/medium
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-tests-v4]]"
---

# Reconciliation focused remediation

Failing acceptance evidence is isolated on test feature
`28ae28f8f353405a873ef903f8346b8a1ed836a1`; it is intentionally not a code
dependency until root merges the production remediation first.

- KS-2 data start must be derived from explicit header-token rows. A non-empty
  detail row must never extend the header boundary merely because it has values in
  the same columns. Preserve the strict explicit quantity + total-cost pair and do
  not weaken the unit aliases.
- A complete state where every group is rejected is a valid authoritative result.
  Publish an immutable verified copy of the target as `result.xlsx`, return feedback,
  and leave every target cell unchanged. Do not call the generic writer with an empty
  write set and do not modify the generic writer.
- Use a focused helper in `reconciliation_target.py` for no-change publication. It
  must refuse an existing output, preserve input bytes, publish atomically, reopen the
  XLSX, and return only after SHA verification. No paths or exceptions enter public
  payloads.
- Do not edit tests. Root integrates the already frozen failing regressions, runs the
  focused suites and performs the real-data/browser smoke.
