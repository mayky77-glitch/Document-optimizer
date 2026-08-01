---
type: task
status: review
work_id: reconciliation-manual-review-full-cards-v2
role: worker
agent_role: developer
owner: "reconciliation-manual-review-full-cards-developer"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Multi-file data-contract and UI implementation must safely enrich privacy-filtered review records and map existing fit/not_fit and approve/reject semantics into full cards."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: "Assigned developer context is runtime-provided; no child override is asserted."
model_fallback: false
last_verified: 2026-08-02
updated: 2026-08-02
write_scope:
  - "src/report_processor/admin_panel/presentation.py"
  - "src/report_processor/admin_panel/service.py"
  - "src/report_processor/admin_panel/app.py"
  - "src/report_processor/admin_panel/assets/admin.js"
  - "src/report_processor/admin_panel/assets/admin.css"
  - "src/report_processor/admin_panel/review_presentation.py"
  - "src/report_processor/admin_panel/review_api.py"
  - "tests/unit/admin_panel/test_presentation.py"
  - "tests/unit/admin_panel/test_service.py"
  - "tests/unit/admin_panel/test_review_presentation.py"
  - "tests/integration/test_block18_admin_panel.py"
  - "knowledge/maps/project-map.md"
source_paths:
  - "src/report_processor/admin_panel/presentation.py"
  - "src/report_processor/admin_panel/service.py"
  - "src/report_processor/admin_panel/app.py"
  - "src/report_processor/admin_panel/assets/admin.js"
  - "src/report_processor/admin_panel/assets/admin.css"
  - "src/report_processor/admin_panel/review_presentation.py"
  - "src/report_processor/admin_panel/review_api.py"
  - "tests/unit/admin_panel/test_presentation.py"
  - "tests/unit/admin_panel/test_service.py"
  - "tests/unit/admin_panel/test_review_presentation.py"
  - "tests/integration/test_block18_admin_panel.py"
  - "knowledge/maps/project-map.md"
depends_on: []
tags:
  - "task/implementation"
  - "status/review"
  - "domain/document-processing"
  - "capability/admin-panel"
  - "layer/backend"
  - "layer/frontend"
  - "risk/medium"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Полные карточки ручной сверки

## Goal

Deliver privacy-safe, information-complete reconciliation review cards at `/`.

## Source-backed inventory

- `QualityIssue` carries controlled `issue_id`, `code`, `severity`, and `message`,
  relation IDs (`target_row_id`, `match_result_id`, `calculation_id`,
  `source_row_ids`), plus `locations` and `evidence`. Presentation must not expose
  the latter two fields.
- `MatchResult` exposes a target row, candidates, units through its rows,
  confidence-bearing candidates, and explanations. `NormalizedSourceRow` exposes
  work name, unit, and numeric source totals. `CalculationResult` exposes a
  derived cost by calculation ID.
- `processing_presentation` currently emits generic issue records and flattens
  every semantic candidate into one suggestion; it drops the issue relation IDs.
- Current decisions are individual suggestion `fit`/`not_fit` and discrepancy
  group `approve`/`reject`; reconciliation has no category or cost-only action.
- `AdminJob.result_available` blocks downloads until both unresolved suggestion
  and manual discrepancy sets are empty. Existing manual decisions validate exact
  open-group membership before mutation.

Route: P4 -> developer / gpt-5.6-terra / high; reason: multi-file, privacy-bound
data contract and atomic decision implementation.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `presentation.py`, new `review_presentation.py`, new
  `review_api.py`, `service.py`, `app.py`, `assets/admin.js`, `assets/admin.css`,
  focused tests and project map.
- Decision contract: manual cards submit only their controlled group ID; server
  reconstructs and atomically resolves the exact open group. Semantic target
  groups submit a real selected candidate; Apply records one `fit` and sibling
  `not_fit` entries, Reject records `not_fit` for all. Both are journal-only.
- Commands and tests run: `.venv/bin/pytest -q tests/unit/admin_panel/test_service.py
  tests/unit/admin_panel/test_presentation.py tests/unit/admin_panel/test_review_presentation.py
  tests/integration/test_block18_admin_panel.py` — `35 passed`; `.venv/bin/ruff check`
  and `.venv/bin/ruff format --check` on all changed Python source/test paths — OK;
  `node --check src/report_processor/admin_panel/assets/admin.js` and `git diff --check` — OK.
  Browser smoke remains for root because the helper invocation cannot start here.
- SHA-256: `presentation.py` `16b4038032bb2841fccc6a11dca1eb9e6163484ad52bab5509979154a9ba9e5f`;
  `review_presentation.py` `9e051f66ec9e814b5b0662bab2e5d08aa53e52e154fe9f3b297ab0f9e7bd87ad`;
  `service.py` `faef328b18935a8c900eeeaa47ce348645610e4541a5622956ca0a8fbc13cf90`;
  `review_api.py` `20f999c3ef9280d34533b375a9284d087d178986f5b4e31b2e06c562610087f1`;
  `app.py` `41f591ef4739b4c7934ca8c825099c50f9f12d75d2d2a64cef65b3c82c53ce5e`;
  `admin.js` `b773404dc8c9b5da7fa980f98e67cb457f2bab2d58864ee429bec833ef1ab5f7`;
  `admin.css` `dc80b83b98d1618c5ee1207d3257f3e2f59bb30247dd4b305388a3b6af65a3d6`.
- Maintainability follow-up: moved reconciliation decision parsing and validation
  into `review_api.py`; `app.py` is 669 lines (down from 689) with unchanged
  endpoint URLs, response statuses, and public error messages.
- Risks or follow-up: visual desktop/mobile light/dark verification remains for
  an environment with dependencies and browser service access.

## Handoff

Leave this card in `review` until orchestration accepts the result.
