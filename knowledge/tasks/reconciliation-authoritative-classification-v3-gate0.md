---
type: orchestration
status: frozen
work_id: reconciliation-authoritative-classification-v3
objective: Replace journal-only reconciliation review with an authoritative source-row classification flow that changes matching, calculation and final XLSX output.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: 3f3b31e4e0aff0905fd0118210817b3425af45d3
published_base_sha_source: root planning commit containing this manifest and frozen Wave 1 cards
wave: 1
max_parallel: 2
max_spawns: 5
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-02T00:00:00+08:00
tags:
  - knowledge/orchestration
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-backend]]"
  - "[[reconciliation-authoritative-ui]]"
  - "[[reconciliation-authoritative-tests]]"
---

# Gate 0: authoritative reconciliation

## Wave graph

1. Wave 1, parallel from the exact planning commit:
   `reconciliation-authoritative-backend` and
   `reconciliation-authoritative-ui`.
2. Wave 2, after both Wave 1 branches are merged and accepted: create/freeze
   `reconciliation-authoritative-integration` in the accepted Wave 1 SHA. Its
   exclusive scope is shared wiring only: `admin_panel/app.py`, `service.py`,
   `presentation.py`, `review_api.py`, `review_presentation.py`,
   `processing/adapters.py`, `excel_writer/engine.py`, and `knowledge/maps/project-map.md`.
3. Wave 3, after Wave 2 acceptance: freeze revision 2 of
   `reconciliation-authoritative-tests` at that exact SHA and launch tester.
4. Final focused reviewer is read-only; no auditor is authorized.

## Shared API contract 1.0

Job payload adds `review_groups`, `review_categories`,
`unresolved_review_count`, and `review_can_apply`. Controlled target category
IDs never expose workbook locations. Group members contain `row_id`, display
name, source unit, quantity and cost only.

Endpoints:

- `PUT /api/jobs/{job_id}/review/groups/{group_id}` with
  `{version, action, category_id, mode}`.
- `PUT|DELETE /api/jobs/{job_id}/review/items/{row_id}` with the same controlled
  decision fields for PUT.
- `POST /api/jobs/{job_id}/review/apply` only when every effective row decision
  is resolved; it reruns matching/calculation/writer from private original inputs.

Allowed actions are `accept` and `reject`; accepted mode is `quantity_cost` or
`cost_only`. Reject forbids category/mode and excludes both values. Group and row
versions reject stale membership/state. Per-row decisions override group state.

## Shared-path policy

Wave 1 cannot edit shared wiring. The Wave 2 integration developer owns all
existing shared backend paths and the project-map update. `app.py` must remain
below the 700-line hard limit; route parsing/handlers belong in focused modules.
No worker starts a local service. Root is the only integration owner.

## Baseline

Commands on parent `3f3b31e4e0aff0905fd0118210817b3425af45d3`:

- `.venv/bin/pytest -q tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_review_presentation.py tests/integration/test_block18_admin_panel.py` — `31 passed in 0.30s`.
- `.venv/bin/ruff check src/report_processor/admin_panel src/report_processor/processing src/report_processor/matching src/report_processor/calculation src/report_processor/excel_writer tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_review_presentation.py tests/integration/test_block18_admin_panel.py` — passed.
- `node --check src/report_processor/admin_panel/assets/admin.js` — passed.

## Release acceptance

- Focused unit/integration tests prove authoritative changes reach match,
  calculation and XLSX cells and suppress repeated review through feedback.
- Ruff check/format, Node syntax and diff-check pass.
- Visual smoke covers 1440/390 px, light/dark, no console errors or horizontal
  overflow.
- No `review_journal_only` or review-journal download remains in the new flow.
- No upstream warnings, provenance or technical metrics appear in review cards.
- UI and workbook-visible numbers are two decimals.
- Knowledge project map and task cards reflect accepted feature/merge SHAs.

## Gate state

This manifest is prepared but not yet open. Root must review and commit it with
the two Wave 1 cards, use that exact commit SHA as `published_base_sha` and
`wave_base_sha` in external ORDA state, create the declared branches/worktrees,
reserve both scopes, then change work status to `running`. Until then no write
worker may launch.
