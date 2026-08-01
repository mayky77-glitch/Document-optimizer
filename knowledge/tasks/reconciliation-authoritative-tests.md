---
type: orda_task
status: frozen
launchable: false
launch_blocker: exact Wave 2 integration SHA is not available at Gate 0
card_id: reconciliation-authoritative-tests
version: 1
supersedes: null
work_id: reconciliation-authoritative-classification-v3
task_id: reconciliation-authoritative-tests
purpose: Prove the integrated authoritative flow changes matches, calculations, feedback suppression, and final XLSX cells.
role: tester
owner: reconciliation-authoritative-tester
card_path: knowledge/tasks/reconciliation-authoritative-tests.md
card_commit_sha_source: exact future Wave 2 card commit supplied by its launch envelope
profile: L1
routing_grade: P3
routing_reason: Focused unit and integration checks must verify the accepted Wave 1 contracts after shared wiring is integrated.
reasoning_effort: medium
assigned_model: gpt-5.6-terra
launch_status: planned
planning_parent_sha: 3f3b31e4e0aff0905fd0118210817b3425af45d3
base_sha_source: must be frozen at the accepted Wave 2 integration SHA
dependency_tasks:
  - reconciliation-authoritative-backend
  - reconciliation-authoritative-ui
  - reconciliation-authoritative-integration
branch: codex/reconciliation-authoritative-tests-v3
branch_base_source: accepted Wave 2 integration SHA
write_scope:
  - tests/unit/reconciliation_review
  - tests/unit/admin_panel/test_authoritative_review.py
  - tests/integration/test_reconciliation_authoritative_flow.py
  - tests/integration/test_block18_admin_panel.py
forbidden_paths:
  - src
  - knowledge/maps
contract_versions:
  input: ReconciliationAuthoritativeIntegrated-1.0
  output: ReconciliationAuthoritativeAcceptance-1.0
acceptance_commands:
  - .venv/bin/pytest -q tests/unit/reconciliation_review tests/unit/admin_panel/test_authoritative_review.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_block18_admin_panel.py
  - .venv/bin/ruff check tests/unit/reconciliation_review tests/unit/admin_panel/test_authoritative_review.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_block18_admin_panel.py
  - .venv/bin/ruff format --check tests/unit/reconciliation_review tests/unit/admin_panel/test_authoritative_review.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_block18_admin_panel.py
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
  - "[[reconciliation-authoritative-classification-v3-gate0|Gate 0]]"
---

# Authoritative reconciliation focused regression

This is a deferred Wave 3 card and is intentionally not reservable at Gate 0.
After Wave 2 shared integration is accepted, freeze a new exact card revision in
that integration SHA and replace `base_sha_source`/dependency task references
with the exact accepted SHAs in the ORDA launch envelope.

## Required evidence

- Grouping spans uploaded files, uses normalized exact/common-prefix name plus
  unit, and preserves every member.
- Accept/reject/other category, two-state mode and per-row override are atomic
  and reject stale versions.
- Applying review changes selected match, Decimal calculation and final XLSX
  quantity/cost cells; `cost_only` leaves quantity untouched/excluded.
- Latest feedback is applied before review generation and suppresses repeats.
- Journal-only result/effect, upstream-warning/provenance and technical metrics
  are absent from the authoritative contract.
- Numeric UI and workbook assertions use two decimals.
