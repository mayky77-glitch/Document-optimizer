---
type: task
card_id: drawing-card-cable-review-v1-tests
status: draft
version: 1
work_id: drawing-card-cable-review-v1
task_id: tests
purpose: "Зафиксировать coupling cost-only, safe grouping, member payload и UI API"
role: worker
agent_role: tester
owner: "tester"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Frozen deterministic backend and UI contracts"
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
card_path: knowledge/tasks/drawing-card-cable-review-v1-tests.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-cable-review-tests
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "tests/unit/drawing_card/test_cable_coupling_family.py"
  - "tests/unit/drawing_card/test_review_clusters.py"
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
  input: "DrawingCardCableReview-1.0+DrawingCardCableReviewUI-1.0"
  output: "DrawingCardCableReviewTests-1.0"
acceptance_commands:
  - "uv run pytest -q tests/unit/drawing_card/test_cable_coupling_family.py tests/unit/drawing_card/test_review_clusters.py tests/unit/drawing_card/test_autopilot_consensus.py tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py"
  - "uv run ruff check tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py"
tags:
  - "task/implementation"
  - "status/draft"
  - "drawing-card"
  - "tests"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Drawing card cable review regressions

## Goal

Cover the exact anchored coupling family, non-matches, cost-only aggregation,
safe cable grouping, complete path-free member payload and category+cost-only API.

## Scope and instructions

- Modify only `write_scope`.
- Never include private source text in committed fixtures.
- Assert prefix-only matching and no inner-substring activation.
- Assert missing cost and formula/Excel hazards remain manual.
- Assert every member is returned once and aggregate cost equals member sum.
- Assert changed category plus `cost_only` fans out atomically.
- Assert filename, sheet, coordinates and paths are absent from payload.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Commit and push the feature branch. Do not merge or force-push.
