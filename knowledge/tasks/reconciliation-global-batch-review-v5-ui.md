---
type: task
status: review
orda_status: review
card_id: reconciliation-global-batch-review-v5-ui
version: 1
work_id: reconciliation-global-batch-review-v5
task_id: ui
purpose: Replace the 500-card screen with accessible responsive package queues and direct controls.
role: worker
agent_role: designer
owner: reconciliation-v5-ui
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: Responsive accessible package interactions with stable direct controls and isolated frontend module.
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: Runtime did not return model confirmation; inherited task execution is recorded against the requested Terra/high route.
model_fallback: true
card_path: knowledge/tasks/reconciliation-global-batch-review-v5-ui.md
card_commit_sha_ref: launch_envelope
base_sha_ref: wave1_integration_sha
dependency_shas_ref:
  - wave1_integration_sha
branch: codex/reconciliation-v5-ui
branch_base_sha_ref: wave1_integration_sha
write_scope:
  - src/report_processor/admin_panel/view.py
  - src/report_processor/admin_panel/assets/reconciliation-batches.js
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/assets/admin.css
  - src/report_processor/admin_panel/assets/index.html
  - tests/integration/test_reconciliation_batch_ui_contract.py
  - tests/integration/test_reconciliation_review_ui_contract.py
source_paths:
  - src/report_processor/admin_panel/view.py
  - src/report_processor/admin_panel/assets/reconciliation-batches.js
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/assets/admin.css
  - src/report_processor/admin_panel/assets/index.html
  - tests/integration/test_reconciliation_batch_ui_contract.py
  - tests/integration/test_reconciliation_review_ui_contract.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/reconciliation_batch_state.py
  - src/report_processor/admin_panel/reconciliation_batch_store.py
  - src/report_processor/admin_panel/reconciliation_batch_presentation.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_review_api.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/drawing_card
contract_versions:
  input: ReconciliationBatchPayload-1.0
  output: ReconciliationBatchUI-1.0
acceptance_commands:
  - node --check src/report_processor/admin_panel/assets/admin.js
  - node --check src/report_processor/admin_panel/assets/reconciliation-batches.js
  - uv run pytest -q tests/integration/test_reconciliation_batch_ui_contract.py tests/integration/test_reconciliation_review_ui_contract.py
  - uv run ruff check tests/integration/test_reconciliation_batch_ui_contract.py tests/integration/test_reconciliation_review_ui_contract.py
  - git diff --check
last_verified: 2026-08-02
updated: 2026-08-02
tags:
  - task/implementation
  - status/draft
  - capability/admin-panel
  - risk/high
links:
  - "[[reconciliation-global-batch-review-v5-core]]"
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Reconciliation global batch review v5 UI

## Frozen contract

- Three queues: `Можно принять пакетом`, `Нужны уточнения`, `Новые виды работ`.
  Default to safe packages. Show short totals and two-decimal quantity/cost.
- One package card: family label, proposed category, direct two-state mode, counts,
  aggregates, short human reason, one accept/reject pair, expandable families/groups/
  rows. No routine modal, dropdown or duplicate confirmation.
- `Принять все безопасные` previews and affects only conflict-free packages. Keep
  card position stable through a short confirmation state. Support one-level undo,
  autosave restoration, pointer/keyboard controls and full visible accessible controls.
- Reuse drawing-card interaction language. Row override wins. Keep light/dark,
  desktop/mobile at 390 px without horizontal overflow.
- Put package UI in `reconciliation-batches.js`; keep `admin.js` below the hard limit.
  Register the new static asset only in `view.py`.

## Completion evidence

- Changed paths: `src/report_processor/admin_panel/assets/reconciliation-batches.js`,
  `src/report_processor/admin_panel/assets/reconciliation-batch-filters.js`,
  `src/report_processor/admin_panel/assets/admin.js`,
  `src/report_processor/admin_panel/assets/admin.css`,
  `src/report_processor/admin_panel/assets/index.html`,
  `src/report_processor/admin_panel/view.py`,
  `tests/integration/test_reconciliation_batch_ui_contract.py`,
  `tests/integration/test_reconciliation_review_ui_contract.py`.
- Commands and tests run: `node --check src/report_processor/admin_panel/assets/admin.js`;
  `node --check src/report_processor/admin_panel/assets/reconciliation-batches.js`;
  `node --check src/report_processor/admin_panel/assets/reconciliation-batch-filters.js`;
  `uv run pytest -q tests/integration/test_reconciliation_batch_ui_contract.py tests/integration/test_reconciliation_review_ui_contract.py`
  (`6 passed`); `uv run ruff check tests/integration/test_reconciliation_batch_ui_contract.py tests/integration/test_reconciliation_review_ui_contract.py`;
  `git diff --check`.
- Result: Package queues consume `ReconciliationBatchPayload-1.0`, with safe-first
  preview/apply, frozen IDs and versions, direct category/mode/action controls at
  package/family/group/row scope, details-based exact membership, keyboard shortcuts,
  session job restoration, undo and responsive light/dark styles. Canonical primary
  filters and compact secondary filters use stable queue values with fail-soft optional
  fields; the authoritative final apply control remains visible when ready.
- Risks or follow-up: Visual browser capture was attempted through the local server,
  but the workspace lacks the Playwright Python package; static 390 px responsive
  contract coverage is included. Lifecycle routes must land before live API exercise.

## Handoff

Leave this card in `review` until ORDA accepts feature and merge SHAs.
