---
type: task
card_id: drawing-card-review-reduction-v3-tests
status: draft
version: 1
work_id: drawing-card-review-reduction-v3
task_id: tests
purpose: "Зафиксировать cluster fanout, feedback reject/conflicts и UI/API контракты"
role: worker
agent_role: tester
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Независимый regression-контракт для backend и UI без production writes"
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
card_path: knowledge/tasks/drawing-card-review-reduction-v3-tests.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-review-tests
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/drawing_card
  - tests/unit/admin_panel/test_drawing_card_service.py
  - tests/integration/test_drawing_card_admin.py
forbidden_paths:
  - src
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - ".env*"
  - "**/*.xlsx"
  - "**/*.xlsm"
  - "**/*.xlsb"
contract_versions:
  input: DrawingCardClusterReview-2.0+ExactFeedbackStore-2.0+DrawingCardClusterReviewUI-2.0
  output: DrawingCardReviewReductionRegression-2.0
acceptance_commands:
  - "uv run pytest -q tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py"
  - "uv run ruff check tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py"
tags:
  - task/tests
  - status/draft
  - drawing-card
  - admin-panel
---

# Test contract

- Canonical clustering reduces the verified 719-row cohort to 254 safe keys.
- Same-name cross-unit rows do not merge.
- Cluster fanout is atomic and stale membership fails.
- Apply remains blocked while any row is unresolved.
- Reject feedback is remembered and exact-unit scoped.
- Conflicting feedback falls back to manual review.
- Formula/Excel-error rows never auto-activate.
- Approve, reject, quantity-only, cost-only and category-change round-trip.
- RuBERT remains suggestion-only.
- Cluster endpoints leak no local paths, filenames, sheets or formulas.
- Existing row endpoints and result generation remain compatible.
