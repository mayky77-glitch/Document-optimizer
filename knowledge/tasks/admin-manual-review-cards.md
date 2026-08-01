---
type: task
status: review
work_id: admin-manual-review-cards-v2-resumed
role: worker
agent_role: developer
owner: "admin_manual_review_developer"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L2 compatibility profile maps to P4."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-02
updated: 2026-08-02
write_scope:
  - "src/report_processor/admin_panel/presentation.py"
  - "src/report_processor/admin_panel/service.py"
  - "src/report_processor/admin_panel/app.py"
  - "src/report_processor/admin_panel/assets/admin.js"
  - "src/report_processor/admin_panel/assets/admin.css"
  - "tests/unit/admin_panel/test_service.py"
  - "tests/unit/admin_panel/test_presentation.py"
  - "tests/integration/test_block18_admin_panel.py"
  - "knowledge/maps/project-map.md"
source_paths:
  - "src/report_processor/admin_panel/presentation.py"
  - "src/report_processor/admin_panel/service.py"
  - "src/report_processor/admin_panel/app.py"
  - "src/report_processor/admin_panel/assets/admin.js"
  - "src/report_processor/admin_panel/assets/admin.css"
  - "tests/unit/admin_panel/test_service.py"
  - "tests/unit/admin_panel/test_presentation.py"
  - "tests/integration/test_block18_admin_panel.py"
  - "knowledge/maps/project-map.md"
depends_on: []
tags:
  - "domain/document-processing"
  - "capability/admin-panel"
  - "layer/backend"
  - "layer/frontend"
  - "risk/medium"
  - "task/implementation"
  - "status/review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Групповые решения по ручным замечаниям сверки

## Goal

Treat quality-control `manual_review` discrepancies as first-class unresolved decisions. Group stable code+message duplicates into compact bulk-review cards, validate an atomic bounded list of exact discrepancy IDs, persist only safe decision metadata, and keep result/download blocked until both suggestion and manual-discrepancy decisions are resolved. Preserve the existing suggestion contract and collapse repeated passive warnings without mixing them into actionable cards.

Real sanitized acceptance shape: `665` discrepancies and no suggestions/decisions must render three actionable groups (`173 + 173 + 146`) and one passive warning group (`173`), not hundreds of rows.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/admin_panel/{service.py,presentation.py,app.py,assets/admin.js,assets/admin.css}`, `tests/unit/admin_panel/{test_service.py,test_presentation.py}`, `tests/integration/test_block18_admin_panel.py`, `knowledge/maps/project-map.md`.
- Commands and tests run: `.venv/bin/pytest -q tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_presentation.py tests/integration/test_block18_admin_panel.py` — `24 passed`; `node --check src/report_processor/admin_panel/assets/admin.js` — passed; `.venv/bin/ruff check` and `.venv/bin/ruff format --check` for changed Python paths — passed; `git diff --check` — passed. `uv run` was unavailable because its cache path was sandbox-denied, so checks used the repository `.venv`.
- Result: manual discrepancies with `category` and `severity` equal to `manual_review` are excluded from passive rows, grouped by controlled code/message, and exposed with exact controlled IDs. `approve`/`reject` validates one exact unresolved group before appending any decision, so unknown, duplicate, partial, and replayed requests cannot mutate a job. Download stays blocked until manual-discrepancy and suggestion decisions are both closed; the existing `fit`/`not_fit` path remains unchanged. UI renders compact Russian cards with count and busy/error/rerender behavior.
- Browser evidence: unavailable — no local Playwright/browser harness is installed (`playwright=unavailable`); no service was started.
- Rerun after restart/schema change: yes. Jobs are in-memory and do not survive restart; no persisted schema changed, but any already-created job must be rerun to receive the new manual-review state.
- Risks or follow-up: journal stores only controlled discrepancy IDs, decisions, and presentation records; raw values, formulae, sheet names, and filesystem paths remain filtered. Evidence SHA-256: `src/report_processor/admin_panel/presentation.py` `7f37fbe93926807d65de4292da33ea4e8edbfda37a52adf6759a40c891067b13`; `service.py` `e154b38b68401b10394e01bcba1d97da9d0ec93a4a3633ba47ba2ccd1587fb47`; `app.py` `e59cdc6846520a818ddcdc5902d2d13eb8fc7f07ae0ec9ac23342d12616deb3b`; `assets/admin.js` `a0d69481ca5dcb74eb5c9f7167145837d5b79a9f60c458afc2a93cd862e3eb5e`; `assets/admin.css` `8a931ca2900aa60f6e7ec137607250bdd3ca1e2aadb2fa65e920ac2e55ba11ec`; `tests/unit/admin_panel/test_service.py` `51676547e1f7f880daf15a4bd3f377042f799ede6873885318284d99b3b8095c`; `test_presentation.py` `ae525977ac3cc263a9957679d5806cc06741764dd48eec38f1e626d87e911345`; `tests/integration/test_block18_admin_panel.py` `b349f686540f5e108f9f74496313334fd68fc057c21b70383b4aa443e1285651`; `knowledge/maps/project-map.md` `838dbc63d0dee5f6d44f89a90e3d0aaa1a46a73da8ad3455c997578283ab1988`.

## Handoff

Leave this card in `review` until orchestration accepts the result.
