---
type: orda_task
status: deferred
card_id: reconciliation-real-data-tests-v4
version: 1
supersedes: null
work_id: reconciliation-real-data-resilience-v4
task_id: reconciliation-real-data-tests-v4
purpose: Add focused unit, integration, real-data and browser acceptance for the accepted production flow.
role: tester
owner: reconciliation-real-data-tester
card_path: knowledge/tasks/reconciliation-real-data-tests-v4.md
profile: L1
routing_grade: P3
routing_reason: Independent focused regression and real-data verification of frozen interfaces.
reasoning_effort: medium
assigned_model: gpt-5.6-terra
launch_status: blocked_on_wave_2
branch: codex/reconciliation-real-data-tests-v4
write_scope:
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/reconciliation_review/test_authoritative_core.py
  - tests/unit/admin_panel/test_service.py
  - tests/unit/admin_panel/test_presentation.py
  - tests/integration/test_reconciliation_authoritative_flow.py
  - tests/integration/test_reconciliation_review_ui_contract.py
  - tests/integration/test_reconciliation_real_data.py
forbidden_paths:
  - src
  - knowledge/maps
contract_versions:
  input: ReconciliationReviewPresentation-2.0
  output: ReconciliationRealDataAcceptance-1.0
tags:
  - task/test
  - status/deferred
  - domain/document-processing
  - capability/admin-panel
  - layer/tests
  - risk/medium
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-resilience-v4-gate0|Gate 0]]"
---

# Reconciliation focused acceptance

This Wave 3 card is intentionally not reservable until the accepted Wave 2 merge SHA
is frozen into its launch envelope and exact acceptance commands are added.

