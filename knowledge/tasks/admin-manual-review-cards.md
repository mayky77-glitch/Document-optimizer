---
type: task
status: done
work_id: admin-manual-review-cards-v2-resumed
role: worker
agent_role: developer
owner: "admin_manual_review_developer"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: "sha256:d21bdb970b57ca7ce56c510647c1dd61f3519fb10b6e0d50ce8e18145334ab89"
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
  - "status/done"
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
- Commands and tests run: `.venv/bin/pytest -q tests/unit/admin_panel/test_service.py tests/unit/admin_panel/test_presentation.py tests/integration/test_block18_admin_panel.py` — `27 passed`; `node --check src/report_processor/admin_panel/assets/admin.js` — passed; `.venv/bin/ruff check` and `.venv/bin/ruff format --check` for changed Python paths — passed; `git diff --check` — passed. `uv run` was unavailable because its cache path was sandbox-denied, so checks used the repository `.venv`.
- Result: discrepancies with `severity=manual_review` are excluded from passive rows, grouped by controlled code/message, and exposed with exact controlled IDs. `approve`/`reject` validates one exact unresolved group before appending any decision, rejects lists above `5000` IDs, and prevents unknown, duplicate, partial, and replayed requests from mutating a job. Identical passive warnings collapse into one row with `count`, while distinct hierarchy fields remain separate. Download stays blocked until manual-discrepancy and suggestion decisions are both closed; the existing `fit`/`not_fit` path remains unchanged. UI renders compact Russian cards and passive repeat counts with busy/error/rerender behavior.
- Browser evidence: static browser fixture was blocked by the in-app browser URL policy; the local service could not bind port `8765` in the managed sandbox. Focused backend/API/DOM-contract tests and direct CSS/JS review passed.
- Rerun after restart/schema change: yes. Jobs are in-memory and do not survive restart; no persisted schema changed, but any already-created job must be rerun to receive the new manual-review state.
- Risks or follow-up: journal stores only controlled discrepancy IDs, decisions, and presentation records; raw values, formulae, sheet names, and filesystem paths remain filtered. Evidence SHA-256: `src/report_processor/admin_panel/presentation.py` `fbcf92157ee369b672558e5d589dc858e388301390cad912ffa14ef74cd6ab9e`; `service.py` `314e97b102d651a020136b77192b8b36d29ec1c4415ade0a823294809f8f7662`; `app.py` `8f2156eda2401dbba256693f893d48bda3f32d73fb7e76d74376c42ba3a3cbde`; `assets/admin.js` `d21bdb970b57ca7ce56c510647c1dd61f3519fb10b6e0d50ce8e18145334ab89`; `assets/admin.css` `01f79b3f58331f7bb846e654957996c94e8eec165681c237782136f7f6c254aa`; `tests/unit/admin_panel/test_service.py` `a374d8782d39a9caa0ebe4d5120b36362601e574da2651dfa444c2023ab80997`; `test_presentation.py` `d6819669215855f02569cecef791f32ff78ba5150f23583cadb5a1c75f93212a`; `tests/integration/test_block18_admin_panel.py` `01a1990adf9295a69621385bbe81c12c3ea1cef6b5e8f183ecb54c7bc1b0f1f8`; `knowledge/maps/project-map.md` `04a555d45068788b2a3ef601a85fcbe232f58f00340e6bcd09a5932edddb0235`.

## Handoff

Orchestration accepted the implementation. User must rerun the reconciliation after restart because jobs are stored in memory.
