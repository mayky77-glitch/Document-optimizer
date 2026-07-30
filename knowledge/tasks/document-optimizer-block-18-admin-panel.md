---
type: task
card_id: document-optimizer-block-18-admin-panel
status: in-progress
version: 1
work_id: document-optimizer-block-18
task_id: block-18-admin-panel
purpose: "Реализовать простую локальную web-панель загрузки, проверки, review и выгрузки"
agent_role: developer
owner: "block-18-admin-panel"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Local upload/download lifecycle, private workspaces and accessible review UI."
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-18-admin-panel.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 0eb32ef6900b607acb5501b18dce131e8c154867
branch: codex/block-18-admin-panel
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block18-admin"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/admin_panel
forbidden_paths:
  - src/report_processor/processing
  - src/report_processor/matching
  - src/report_processor/stage_rag
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
  - .github
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  admin_panel: LocalAdminPanel-18.0
acceptance_commands:
  - "uv run ruff check src/report_processor/admin_panel"
  - "uv run ruff format --check src/report_processor/admin_panel"
  - "uv run python -m compileall -q src/report_processor/admin_panel"
tags:
  - task/implementation
  - status/in-progress
  - layer/frontend
  - risk/high
---

# Block 18 local admin panel

Build one local-only screen. The user uploads source/target XLSX, chooses a
stage (default 13.1), runs the pipeline, reviews uncertain semantic relations,
and downloads output or a controlled-ID review journal. Use Gazprom blue
`#0079C2` for the interface. Red/yellow/orange/blue are discrepancy semantics.
No external assets, raw server paths, workbook mutation, or implicit approval.
