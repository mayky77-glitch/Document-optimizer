---
type: task
card_id: drawing-card-admin-v1-production
status: done
version: 1
work_id: drawing-card-admin-v1
task_id: production
purpose: "Перенести deterministic drawing-card workflow и создать приватный admin service"
role: worker
agent_role: developer
owner: drawing-card-production
profile: L1
routing_grade: P3
routing_reason: "Port of a multi-module Excel workflow, package resources and private review lifecycle."
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
progress_revision: 1
state_fingerprint: "59ccb5f0536521ed96ac92cb315a9dab8055cb684ffac18b025607c5aa6f49f5"
no_progress_count: 0
circuit_state: closed
luna_benchmark_evidence: ""
exception_evidence: ""
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/drawing-card-admin-v1-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - b8db88e43b0bf54ac31f4b39c9413ae93d50627e
branch: codex/drawing-card-production
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/drawing_card
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
source_paths:
  - src/report_processor/drawing_card
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
depends_on: []
forbidden_paths:
  - src/report_processor/admin_panel/assets
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/view.py
  - src/report_processor/admin_panel/__init__.py
  - src/report_processor/cli.py
  - pyproject.toml
  - uv.lock
  - tests
  - docs
  - README.md
  - knowledge
  - .github
  - ".env*"
  - "**/*.zip"
contract_versions:
  input: DrawingCardWorkflow-0.9.1-adapter-1.0
  output: DrawingCardAdminJob-1.0
  resources: DrawingCardResources-1.0
acceptance_commands:
  - "uv run ruff check src/report_processor/drawing_card src/report_processor/admin_panel/drawing_card_*.py"
  - "uv run ruff format --check src/report_processor/drawing_card src/report_processor/admin_panel/drawing_card_*.py"
  - "uv run python -m compileall -q src/report_processor/drawing_card src/report_processor/admin_panel"
tags:
  - task/implementation
  - status/done
  - layer/backend
  - risk/high
---

# Drawing-card production

Port only the `drawing_card` package from the read-only source snapshot. Do not
copy its CLI, package metadata, caches, work/output directories or external
model configuration. Package rules, examples and the default template as
`importlib.resources`; admin defaults to deterministic `rag_mode=off`.

Create a private job service for create/update and review re-run. The service
accepts only explicit uploaded files, never ZIP or directories, and never
publishes private paths or raw audit artifacts.

Completion evidence: private service, bundled resources and workflow integrated;
safe filename/magic/size validation; opaque repr; identity-preserving private
staging; focused real demo `1 passed`; full regression `604 passed`.
