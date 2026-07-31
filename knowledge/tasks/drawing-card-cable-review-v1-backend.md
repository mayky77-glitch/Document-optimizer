---
type: task
card_id: drawing-card-cable-review-v1-backend
status: draft
version: 1
work_id: drawing-card-cable-review-v1
task_id: backend
purpose: "Добавить guarded cost-only для соединительных муфт и прозрачный cluster payload"
role: worker
agent_role: developer
owner: "developer"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Financial matcher semantics and safe grouping span multiple contracts"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/drawing-card-cable-review-v1-backend.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-cable-review-backend
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "src/report_processor/drawing_card/resources/rules.json"
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "src/report_processor/drawing_card/review/clusters.py"
  - "src/report_processor/drawing_card/review/grouping.py"
  - "src/report_processor/admin_panel/drawing_card_service.py"
  - "src/report_processor/admin_panel/drawing_card_review_payload.py"
source_paths:
  - "src/report_processor/drawing_card/resources/rules.json"
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "src/report_processor/drawing_card/review/clusters.py"
  - "src/report_processor/admin_panel/drawing_card_service.py"
depends_on: []
forbidden_paths:
  - "src/report_processor/admin_panel/assets"
  - "tests"
  - "docs"
  - "README.md"
  - "pyproject.toml"
  - "uv.lock"
  - ".env*"
  - "**/*.xlsx"
  - "**/*.xlsm"
  - "**/*.xlsb"
contract_versions:
  input: "DrawingCardClusterReview-2.0"
  output: "DrawingCardCableReview-1.0"
acceptance_commands:
  - "uv run ruff check src/report_processor/drawing_card src/report_processor/admin_panel/drawing_card_service.py src/report_processor/admin_panel/drawing_card_review_payload.py"
  - "uv run python -m compileall -q src/report_processor/drawing_card src/report_processor/admin_panel"
tags:
  - "task/implementation"
  - "status/draft"
  - "drawing-card"
  - "matching"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Drawing card cable review backend

## Goal

Classify names beginning with `Установка муфт соединительных` as
`power_cable/cost_only`, expose every safe member row and exact aggregate cost,
and group only controlled cable prefixes without erasing brand, type or mass.

## Scope and instructions

- Modify only `write_scope`.
- Prefix must be anchored at normalized name start.
- Missing/non-positive cost, formula/Excel hazard, negative rule or feedback conflict stays fail-closed.
- Do not use broad inner substring `муфт`.
- Preserve semantic suffixes: brand, mark, model, article, section, voltage and mass.
- Payload contains every member once, stable order, quantity/cost and no path/filename/sheet/coordinates.
- Keep cluster identity membership-based so changed membership is stale.
- Avoid growing `drawing_card_service.py`; move payload shaping into the new focused module.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Commit and push the feature branch. Do not merge or force-push.
