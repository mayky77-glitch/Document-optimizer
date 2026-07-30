---
type: task
card_id: document-optimizer-block-18-admin-tests
status: in-progress
version: 1
work_id: document-optimizer-block-18
task_id: block-18-admin-tests
purpose: "Проверить local-only API, uploads, review decisions, downloads и UI semantics"
agent_role: tester
owner: "block-18-admin-tests"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded admin API and presentation contract tests without production edits."
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-18-admin-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 0eb32ef6900b607acb5501b18dce131e8c154867
branch: codex/block-18-admin-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block18-admin-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/admin_panel
  - tests/integration/test_block18_admin_panel.py
forbidden_paths:
  - src
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
  - "uv run ruff check tests/unit/admin_panel tests/integration/test_block18_admin_panel.py"
  - "uv run pytest -q tests/unit/admin_panel tests/integration/test_block18_admin_panel.py"
tags:
  - task/implementation
  - status/in-progress
  - layer/test
  - risk/medium
---

# Block 18 admin tests

Use temporary fake XLSX bytes and injected processing services. Verify
local-only defaults, upload validation, explicit review decisions, safe
downloads, no-clobber/private cleanup, and stable discrepancy color codes.
