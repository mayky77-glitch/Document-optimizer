---
type: orda_task
status: frozen
orda_status: frozen_in_core_integration_merge
card_id: reconciliation-authoritative-admin-v3
card_path: knowledge/tasks/reconciliation-authoritative-admin-v3.md
version: 1
supersedes: reconciliation-authoritative-backend
work_id: reconciliation-authoritative-admin-v3
task_id: reconciliation-authoritative-admin-v3
purpose: Wire persisted authoritative group and row decisions into one verified global rerun and final XLSX result.
role: developer
owner: reconciliation-authoritative-admin-developer
profile: L2
routing_grade: P4
routing_reason: Stateful API, SQLite feedback, private workbook adapters and lifecycle replacement require difficult multi-file integration.
reasoning_effort: high
assigned_model: gpt-5.6-terra
launch_status: planned
base_sha_source: exact accepted core merge supplied by Gate 0 envelope
dependency_shas:
  - 9a69de210563a58634994c731ce3e5e383af7e1a
branch: codex/reconciliation-authoritative-admin-v3
branch_base_source: exact accepted core merge supplied by Gate 0 envelope
write_scope:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/reconciliation_review_api.py
  - src/report_processor/admin_panel/reconciliation_review_presentation.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/reconciliation_feedback_store.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/processing/adapters.py
forbidden_paths:
  - src/report_processor/reconciliation_review
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/quality_control
  - src/report_processor/excel_writer
  - tests
  - knowledge/maps
contract_versions:
  input: ReconciliationAuthoritativeCore-1.0
  output: ReconciliationAuthoritativeAdmin-1.0
acceptance_commands:
  - .venv/bin/pytest -q tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_review_presentation.py tests/integration/test_block18_admin_panel.py
  - .venv/bin/ruff check src/report_processor/admin_panel src/report_processor/processing/adapters.py
  - .venv/bin/ruff format --check src/report_processor/admin_panel src/report_processor/processing/adapters.py
  - node --check src/report_processor/admin_panel/assets/admin.js
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
  - layer/backend
  - risk/high
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-admin-v3-gate0|Gate 0]]"
---

# Authoritative admin integration

## Required behavior

- `ReconciliationReviewState` owns latest group decisions and row overrides.
  Versions hash source/target digests, membership, catalog and relevant decision
  state. PUT and row DELETE are atomic; stale versions fail without mutation.
- Four route handlers live in `reconciliation_review_routes.py`: group PUT, row
  PUT/DELETE, final apply POST. Path identity is authoritative; body cannot switch
  group/row. Unknown category is rejected.
- `ReconciliationFeedbackStore` uses a private SQLite file under workspace root,
  target scope, monotonic sequence and latest-wins records. Feedback becomes
  durable only after a verified XLSX write; persistence failure removes output
  and leaves job non-ready.
- `reconciliation_execution.py` supplies real private workbook adapters to the
  global core, uses every original source at once, binds category IDs to target
  rows, and writes once against the original target. Never chain intermediate
  workbooks or accept cached artifacts as authority.
- `AdminPanelService` exposes safe review payload/state methods and final XLSX.
  Remove `review-journal.json` and `review_recorded` as successful outcomes for
  this flow. Existing legacy endpoints may remain only where unrelated UI/tests
  still need them; new UI uses authoritative endpoints exclusively.
- Presentation shows short Russian summary, safe global groups and category
  labels. Hide technical English metrics, upstream warning cards and evidence.
  Every displayed numeric value is formatted with two decimals.
- Align Wave 1 UI/backend field names (`category_id`, opaque string versions) and
  fix direct two-state/group/row operations. No dropdown for the two-state mode.
- Keep `app.py` under 700 lines by route delegation. Do not grow `service.py`
  beyond 600 lines; move state, persistence and workbook execution into owned
  focused modules.

## Handoff

Commit and push the feature branch. Return exact feature SHA, changed paths,
focused checks, lifecycle/persistence risks and integration order. Frozen card
bytes remain unchanged; do not merge or force-push after handoff.
