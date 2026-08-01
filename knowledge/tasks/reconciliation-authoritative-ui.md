---
type: orda_task
status: frozen
card_id: reconciliation-authoritative-ui
version: 1
supersedes: null
work_id: reconciliation-authoritative-classification-v3
task_id: reconciliation-authoritative-ui
purpose: Replace journal-style cards with the frozen authoritative review interaction in the existing reconciliation assets.
role: designer
owner: reconciliation-authoritative-designer
card_path: knowledge/tasks/reconciliation-authoritative-ui.md
card_commit_sha_source: exact planning commit supplied by Gate 0 launch envelope
profile: L2
routing_grade: P4
routing_reason: Responsive review cards require category, direct two-state mode, group action, and per-row override in both themes.
reasoning_effort: high
assigned_model: gpt-5.6-terra
launch_status: planned
planning_parent_sha: 3f3b31e4e0aff0905fd0118210817b3425af45d3
base_sha_source: exact planning commit supplied by Gate 0 launch envelope
dependency_shas: []
branch: codex/reconciliation-authoritative-ui-v3
branch_base_source: exact planning commit supplied by Gate 0 launch envelope
write_scope:
  - src/report_processor/admin_panel/assets/index.html
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/assets/admin.css
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/review_api.py
  - src/report_processor/admin_panel/review_presentation.py
  - src/report_processor/reconciliation_review
  - tests
  - knowledge/maps
contract_versions:
  input: ReconciliationAuthoritativeReviewPayload-1.0
  output: ReconciliationAuthoritativeReviewInteraction-1.0
acceptance_commands:
  - node --check src/report_processor/admin_panel/assets/admin.js
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
  - layer/frontend
  - risk/medium
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-classification-v3-gate0|Gate 0]]"
---

# Authoritative reconciliation UI

## Frozen contract

- Consume `review_groups`, `review_categories`, `unresolved_review_count` and
  `review_can_apply` from the job payload. A group contains controlled
  `group_id`, `version`, proposed/selected category, mode, and every member.
- Card actions are one category select, a direct two-state segmented switch
  `Количество + стоимость` / `Только стоимость`, `Принять` and `Отклонить`.
  No dropdown/modal for the two-state mode and no duplicated category buttons.
- Every member row is visible in the expandable composition and has a compact
  `Изменить строку` override using the same category/mode/action contract.
- Group PUT sends `{version, action, category_id, mode}`. Row PUT sends
  `{version, action, category_id, mode}`. Row DELETE removes its override.
  Final POST applies the complete resolved review and triggers authoritative rerun.
- Hide upstream warnings, provenance, evidence IDs and technical metrics.
  Quantity/cost display uses exactly two decimals.
- Reuse the existing theme preference. Actions wrap without page or card
  horizontal overflow at 390 px and remain keyboard accessible.

## Frozen endpoints

- `PUT /api/jobs/{job_id}/review/groups/{group_id}`
- `PUT|DELETE /api/jobs/{job_id}/review/items/{row_id}`
- `POST /api/jobs/{job_id}/review/apply`

## Handoff evidence

Move to `review` only with changed paths, feature SHA, Node/diff-check results,
four visual-smoke captures, console status, overflow measurements and risks.
Do not edit backend or tests and do not merge.
