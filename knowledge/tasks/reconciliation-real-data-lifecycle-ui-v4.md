---
type: orda_task
status: deferred
card_id: reconciliation-real-data-lifecycle-ui-v4
version: 1
supersedes: null
work_id: reconciliation-real-data-resilience-v4
task_id: reconciliation-real-data-lifecycle-ui-v4
purpose: Preserve safe upload names, integrate source issues, and present clear grouped reconciliation cards.
role: developer
owner: reconciliation-real-data-lifecycle-ui-developer
card_path: knowledge/tasks/reconciliation-real-data-lifecycle-ui-v4.md
profile: L1
routing_grade: P3
routing_reason: Scoped lifecycle and responsive frontend integration after the source contract is accepted.
reasoning_effort: medium
assigned_model: gpt-5.6-terra
launch_status: blocked_on_wave_1
branch: codex/reconciliation-real-data-lifecycle-ui-v4
write_scope:
  - src/report_processor/admin_panel/reconciliation_uploads.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/reconciliation_review_presentation.py
  - src/report_processor/admin_panel/assets/index.html
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/assets/admin.css
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/reconciliation_review
  - src/report_processor/processing
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - tests
contract_versions:
  input: ReconciliationSourceBatch-1.0
  output: ReconciliationReviewPresentation-2.0
tags:
  - task/implementation
  - status/deferred
  - domain/document-processing
  - capability/admin-panel
  - layer/full-stack
  - risk/medium
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-resilience-v4-gate0|Gate 0]]"
---

# Reconciliation lifecycle and UI

This Wave 2 card is intentionally not reservable until the accepted Wave 1 merge SHA
is frozen into its launch envelope and exact acceptance commands are added.

