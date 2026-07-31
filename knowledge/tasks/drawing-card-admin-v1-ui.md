---
type: task
card_id: drawing-card-admin-v1-ui
status: done
version: 1
work_id: drawing-card-admin-v1
task_id: ui
purpose: "Добавить понятную навигацию и отдельный экран карточки остатков"
role: worker
agent_role: designer
owner: drawing-card-ui
profile: L2
routing_grade: P4
routing_reason: "Responsive local-only UI with two workflows, upload/review states and accessibility."
assigned_model: gpt-5.6-terra
reasoning_effort: high
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
launch_status: confirmed
progress_revision: 1
state_fingerprint: "571eafb5900809789ef3c4497a7fc847df93d1818a8ff920806f25f8b12f69f6"
no_progress_count: 0
circuit_state: closed
luna_benchmark_evidence: ""
exception_evidence: ""
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/drawing-card-admin-v1-ui.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - b8db88e43b0bf54ac31f4b39c9413ae93d50627e
branch: codex/drawing-card-ui
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/admin_panel/assets
source_paths:
  - src/report_processor/admin_panel/assets
depends_on: []
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/view.py
  - src/report_processor/admin_panel/__init__.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - tests
  - pyproject.toml
  - uv.lock
  - docs
  - README.md
  - knowledge
  - .github
  - ".env*"
contract_versions:
  input: DrawingCardAdminJob-1.0
  output: DrawingCardUI-1.0
acceptance_commands:
  - "node --check src/report_processor/admin_panel/assets/admin.js"
  - "node --check src/report_processor/admin_panel/assets/drawing-card.js"
  - "git diff --check -- src/report_processor/admin_panel/assets"
tags:
  - task/implementation
  - status/done
  - layer/frontend
  - risk/high
---

# Drawing-card UI

Use `$frontend-design`. Preserve Gazprom blue `#0079C2` and existing discrepancy
semantics. Add two direct top-level workflow choices and two direct operation
choices; no dropdown for two-state controls. New screen uses local assets only,
clear next actions, keyboard focus, reduced motion and mobile width 360px.

Completion evidence: separate `/drawing-card` screen, direct create/update,
Gazprom-blue local assets, responsive desktop/mobile layout, keyboard focus,
successful browser create/download flow and zero external/error events.
