---
type: task
card_id: drawing-card-review-reduction-v3-backend
status: draft
version: 1
work_id: drawing-card-review-reduction-v3
task_id: backend
purpose: "Реализовать безопасные review-кластеры и exact feedback с памятью reject"
role: worker
agent_role: developer
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Многофайловый backend-контракт, атомарный fanout и приватная память решений"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
card_path: knowledge/tasks/drawing-card-review-reduction-v3-backend.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-review-backend
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/drawing_card/review
  - src/report_processor/drawing_card/matching/examples.py
  - src/report_processor/drawing_card/matching/matcher.py
  - src/report_processor/drawing_card/workflow.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - src/report_processor/admin_panel/app.py
forbidden_paths:
  - src/report_processor/admin_panel/assets
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - ".env*"
  - "**/*.xlsx"
  - "**/*.xlsm"
  - "**/*.xlsb"
contract_versions:
  input: DrawingCardInlineReview-1.0+ReviewFeedbackStore-1.0
  output: DrawingCardClusterReview-2.0+ExactFeedbackStore-2.0
acceptance_commands:
  - "uv run ruff check src/report_processor/drawing_card/review src/report_processor/drawing_card/matching src/report_processor/drawing_card/workflow.py src/report_processor/admin_panel/drawing_card_service.py src/report_processor/admin_panel/drawing_card_presentation.py src/report_processor/admin_panel/app.py"
  - "uv run python -m compileall -q src/report_processor/drawing_card src/report_processor/admin_panel"
tags:
  - task/implementation
  - status/draft
  - drawing-card
  - matching
---

# Backend contract

- Cluster key uses production `normalize_text(name)` and `normalize_unit(unit)`.
- Split clusters on formula/error hazard, proposed category, decision shape,
  controlled source type and reason code.
- One cluster action atomically applies one decision to all current members.
- Changed membership or stale cluster identity rejects the action without partial writes.
- Existing row API remains compatible.
- Exact feedback learns approve, reject, quantity-only, cost-only and category change.
- Negative feedback is exact and unit-scoped.
- Conflicting exact feedback returns to manual review; never first/last-write auto-selection.
- Formula/Excel-error rows never auto-activate from feedback.
- RuBERT remains suggestion-only.
- Feedback persistence must not store filenames, paths, sheets, credentials or raw formulas.
