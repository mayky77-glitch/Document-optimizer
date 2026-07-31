---
type: task
card_id: drawing-card-autopilot-review-v1-backend
status: draft
version: 1
work_id: drawing-card-autopilot-review-v1
task_id: backend
purpose: "Сократить review через fail-closed machine consensus и strong-rule cost-only"
role: worker
agent_role: developer
owner: "developer"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Fail-closed machine consensus, strong-rule cost-only and exact provenance"
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
card_path: knowledge/tasks/drawing-card-autopilot-review-v1-backend.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-autopilot-backend
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "src/report_processor/drawing_card/autopilot"
  - "src/report_processor/drawing_card/matching/examples.py"
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/workflow.py"
  - "src/report_processor/admin_panel/drawing_card_service.py"
source_paths:
  - "src/report_processor/drawing_card/autopilot"
  - "src/report_processor/drawing_card/matching/examples.py"
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/workflow.py"
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
  input: "DrawingCardClusterReview-2.0+MachineConsensusDraft-1.0"
  output: "DrawingCardReviewAutopilot-1.0"
acceptance_commands:
  - "uv run ruff check src/report_processor/drawing_card src/report_processor/admin_panel/drawing_card_service.py"
  - "uv run python -m compileall -q src/report_processor/drawing_card src/report_processor/admin_panel"
tags:
  - "task/implementation"
  - "status/draft"
  - "drawing-card"
  - "matching"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Drawing card review autopilot backend

## Goal

Add a separate machine-consensus store and fail-closed exact activation. Automatically
resolve only strong unique-rule unit mismatches as cost-only. Keep human feedback separate.

## Scope and instructions

- Modify only `write_scope` paths.
- Machine consensus is exact name + unit + source type + rules version.
- `confirmed_by` must never claim a human decision.
- Hazards, conflicts, stale fingerprints, unknown categories and schema errors stay manual.
- RuBERT score/category never participates in consensus activation.
- Deleting the machine artifact must restore the current cluster behavior.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
