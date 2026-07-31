---
type: task
card_id: drawing-card-autopilot-review-v1-tests
status: draft
version: 1
work_id: drawing-card-autopilot-review-v1
task_id: tests
purpose: "Зафиксировать fail-closed autopilot и real-data action floor"
role: worker
agent_role: tester
owner: "tester"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Focused auto-resolution and consensus regression coverage"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/drawing-card-autopilot-review-v1-tests.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-autopilot-tests
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "tests/unit/drawing_card"
  - "tests/unit/admin_panel/test_drawing_card_service.py"
  - "tests/integration/test_drawing_card_admin.py"
source_paths:
  - "tests/unit/drawing_card"
  - "tests/unit/admin_panel/test_drawing_card_service.py"
  - "tests/integration/test_drawing_card_admin.py"
depends_on: []
forbidden_paths:
  - "src"
  - "docs"
  - "README.md"
  - "pyproject.toml"
  - "uv.lock"
  - ".env*"
  - "**/*.xlsx"
  - "**/*.xlsm"
  - "**/*.xlsb"
contract_versions:
  input: "DrawingCardReviewAutopilot-1.0"
  output: "DrawingCardReviewAutopilotTests-1.0"
acceptance_commands:
  - "uv run pytest -q tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py"
  - "uv run ruff check tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py"
tags:
  - "task/implementation"
  - "status/draft"
  - "drawing-card"
  - "tests"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Drawing card review autopilot regressions

## Goal

Cover strong-rule cost-only, separate machine provenance, exact scope, stale rules,
hazard/conflict fallback, rollback, and the private replay gate of at most 25 actions.

## Scope and instructions

- Modify only `write_scope` paths.
- Never weaken existing RuBERT suggestion-only tests.
- Assert unsafe automatic quantity count is zero.
- Keep private row text out of committed fixtures and test output.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
