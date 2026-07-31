---
type: task
card_id: drawing-card-review-reduction-v2-ui
status: draft
version: 1
work_id: drawing-card-review-reduction-v2
task_id: ui
purpose: "Переключить ручную проверку на cluster-first интерфейс"
role: worker
agent_role: designer
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Новый responsive review-flow с прямыми действиями и доступностью"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
card_path: knowledge/tasks/drawing-card-review-reduction-v2-ui.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-review-ui
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/admin_panel/assets/drawing-card.html
  - src/report_processor/admin_panel/assets/drawing-card.css
  - src/report_processor/admin_panel/assets/drawing-card.js
  - src/report_processor/admin_panel/assets/drawing-card-review.js
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - src/report_processor/drawing_card
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - ".env*"
contract_versions:
  input: DrawingCardClusterReviewAPI-2.0
  output: DrawingCardClusterReviewUI-2.0
acceptance_commands:
  - "node --check src/report_processor/admin_panel/assets/drawing-card.js"
  - "node --check src/report_processor/admin_panel/assets/drawing-card-review.js"
tags:
  - task/design
  - status/draft
  - drawing-card
  - admin-panel
---

# UI contract

- Cluster cards are the default; member rows expand only on demand.
- Show work name, unit, member count, proposed category, reason and confidence.
- Direct actions: approve, reject, cost-only. Category change may use the existing selector.
- Remove global approve-all from the primary flow.
- Show unresolved cluster count and affected row count separately.
- Preserve keyboard focus, visible focus state, mobile layout and reduced motion.
- Keep user copy Russian and action-oriented.
- Move review behavior into `drawing-card-review.js`; do not grow the existing
  `drawing-card.js` beyond its current size.
