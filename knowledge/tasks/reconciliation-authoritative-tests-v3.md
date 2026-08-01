---
type: orda_task
status: frozen
orda_status: frozen_in_admin_integration_merge
card_id: reconciliation-authoritative-tests-v3
card_path: knowledge/tasks/reconciliation-authoritative-tests-v3.md
version: 1
supersedes: reconciliation-authoritative-tests
work_id: reconciliation-authoritative-tests-v3
task_id: reconciliation-authoritative-tests-v3
purpose: Add focused regression evidence for authoritative global review and remove obsolete passive-card expectations.
role: tester
owner: reconciliation-authoritative-tester
profile: L1
routing_grade: P3
routing_reason: Focused tests and fixtures must exercise integrated production contracts without changing them.
reasoning_effort: medium
assigned_model: gpt-5.6-terra
launch_status: planned
base_sha_source: exact accepted admin merge supplied by Gate 0 envelope
dependency_shas:
  - 9a69de210563a58634994c731ce3e5e383af7e1a
  - 736beb8266765e2e8026aa0c248e25c798125216
branch: codex/reconciliation-authoritative-tests-v3
branch_base_source: exact accepted admin merge supplied by Gate 0 envelope
write_scope:
  - tests/unit/reconciliation_review/test_authoritative_core.py
  - tests/unit/admin_panel/test_reconciliation_state.py
  - tests/unit/admin_panel/test_reconciliation_feedback_store.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_authoritative_review.py
  - tests/integration/test_reconciliation_authoritative_flow.py
  - tests/integration/test_block13_authoritative_multi_selection.py
  - tests/integration/test_block14_authoritative_multi_selection.py
  - tests/integration/test_block18_admin_panel.py
  - tests/integration/test_reconciliation_review_ui_contract.py
forbidden_paths:
  - src
  - knowledge/maps
contract_versions:
  input: ReconciliationAuthoritativeAdmin-1.0
  output: ReconciliationAuthoritativeAcceptance-1.0
acceptance_commands:
  - .venv/bin/pytest -q tests/unit/reconciliation_review/test_authoritative_core.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_authoritative_review.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_block13_authoritative_multi_selection.py tests/integration/test_block14_authoritative_multi_selection.py tests/integration/test_block18_admin_panel.py tests/integration/test_reconciliation_review_ui_contract.py
  - .venv/bin/ruff check tests/unit/reconciliation_review/test_authoritative_core.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_authoritative_review.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_block13_authoritative_multi_selection.py tests/integration/test_block14_authoritative_multi_selection.py tests/integration/test_block18_admin_panel.py tests/integration/test_reconciliation_review_ui_contract.py
  - .venv/bin/ruff format --check tests/unit/reconciliation_review/test_authoritative_core.py tests/unit/admin_panel/test_reconciliation_state.py tests/unit/admin_panel/test_reconciliation_feedback_store.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_authoritative_review.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_block13_authoritative_multi_selection.py tests/integration/test_block14_authoritative_multi_selection.py tests/integration/test_block18_admin_panel.py tests/integration/test_reconciliation_review_ui_contract.py
  - node --check src/report_processor/admin_panel/assets/admin.js
  - git diff --check
tags:
  - task/test
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
  - layer/test
  - risk/medium
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-tests-v3-gate0|Gate 0]]"
---

# Authoritative reconciliation focused regression

## Required evidence

- Two source files form one global normalized group containing every row.
- Two rows accepted into one target aggregate quantity and cost once; arbitrary
  target choice creates an explicit authoritative candidate.
- Row decision wins over group. Reject contributes neither value. `cost_only`
  changes cost and leaves original target quantity cell untouched.
- Group and exact row feedback persist latest-wins; row feedback overrides group;
  same target suppresses resolved cards; another target ignores it.
- Group/row PUT and row DELETE reject stale versions without partial mutation.
  Apply before zero unresolved rows does not write. Tampered source/target blocks.
- Writer success followed by feedback failure removes output and stays non-ready.
- Safe payload has categories, unresolved row count and two-decimal numbers, but
  no paths, sheets, coordinates, provenance, warnings, technical metrics or
  `review_journal_only`.
- Update the two old Block 18 assertions: passive discrepancy/warning CSS is no
  longer required; authoritative group/row controls and local responsive assets
  are required instead.

## Handoff

Commit and push the test-only branch. Return exact feature SHA, changed paths,
focused command results and missing coverage. Do not edit production or merge.
