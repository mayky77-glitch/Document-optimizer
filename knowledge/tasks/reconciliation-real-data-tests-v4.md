---
type: orda_task
status: frozen
card_id: reconciliation-real-data-tests-v4
version: 2
supersedes: null
work_id: reconciliation-real-data-tests-v4
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
launch_status: planned
planning_parent_sha: e0eba998137c2b7da9794ad0ffeba9ad5b4d0053
base_sha_source: exact Wave 3 planning commit supplied by the launch envelope
dependency_shas:
  - e0eba998137c2b7da9794ad0ffeba9ad5b4d0053
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
acceptance_commands:
  - .venv/bin/pytest -q tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/reconciliation_review/test_authoritative_core.py tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_presentation.py
  - .venv/bin/pytest -q tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_reconciliation_review_ui_contract.py tests/integration/test_reconciliation_real_data.py
  - .venv/bin/ruff check tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/reconciliation_review/test_authoritative_core.py tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_presentation.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_reconciliation_review_ui_contract.py tests/integration/test_reconciliation_real_data.py
  - .venv/bin/ruff format --check tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/reconciliation_review/test_authoritative_core.py tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_presentation.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_reconciliation_review_ui_contract.py tests/integration/test_reconciliation_real_data.py
tags:
  - task/test
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
  - layer/tests
  - risk/medium
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-resilience-v4-gate0|Gate 0]]"
---

# Reconciliation focused acceptance

## Frozen acceptance contract

- Test only the accepted production flow at dependency SHA
  `e0eba998137c2b7da9794ad0ffeba9ad5b4d0053`; do not edit production code.
- Cover partial-source continuation, all-source controlled failure, safe original
  basename guidance, target A/B/C/D/E/F/J/K binding, grouped proposals and exact
  membership without duplication.
- Cover group fan-out, row override priority, both `quantity_cost` and `cost_only`,
  incomplete-review apply rejection, feedback restoration and verified XLSX output.
- The cost oracle uses raw source rubles multiplied by `2.7`, then divides by
  `1_000_000` and rounds half-up to two decimals at the target adapter boundary.
  Quantity output is rounded half-up to two decimals.
- The real-data test is opt-in through environment variables and must assert that
  every input SHA stays unchanged. Never hard-code private paths, basenames, sheet
  names, coordinates, formulas, provenance or evidence in the test or vault.
- Public payload assertions must reject paths, sheets, coordinates, formulas,
  provenance/evidence, exceptions and raw technical warnings.
- UI contract must preserve one category selector, a direct two-position mode
  switch, group accept/reject, expandable complete members and row override.
- Do not run the full suite. Report exact focused counts, Ruff/format results,
  changed paths and residual risks.
