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

- Changed paths: `presentation.py`, new `review_presentation.py`, `service.py`,
  `app.py`, `assets/admin.js`, `assets/admin.css`, focused tests and project map.
- Decision contract: manual cards submit only their controlled group ID; server
  reconstructs and atomically resolves the exact open group. Semantic target
  groups submit a real selected candidate; Apply records one `fit` and sibling
  `not_fit` entries, Reject records `not_fit` for all. Both are journal-only.
- Commands and tests run: `node --check .../admin.js`, `python3 -m compileall -q
  src/report_processor/admin_panel`, `git diff --check` — passed. Focused pytest
  is blocked by missing local `duckdb`; `uv run ruff` is blocked by the sandboxed
  cache/runtime panic. Browser smoke is unavailable because the skill helper is
  invoked as `python` but only `python3` exists; no service retry was attempted.
- SHA-256: `presentation.py` 3844dc7f2e5b8eb422b7254a9b645608df37a0d57a28e6c89a0ce8e6bcb30789;
  `review_presentation.py` is recorded in the commit diff.
- Risks or follow-up: visual desktop/mobile light/dark verification remains for
  an environment with dependencies and browser service access.

## Handoff

Leave this card in `review` until orchestration accepts the result.
