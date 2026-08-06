---
type: task
status: frozen
card_id: drawing-card-workbook-review-lifecycle
version: 1
supersedes: null
work_id: drawing-card-ux-workbook-review-lifecycle-v1
task_id: workbook-review-lifecycle
purpose: Make sequential workbook review generations and failed-transition retry safe.
role: developer
card_path: knowledge/tasks/drawing-card-workbook-review-lifecycle.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - ee2dc933b307a0c850751632b6ee461b5547df4a
branch: codex/drawing-card-workbook-review-lifecycle
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_service.py
  - tests/integration/test_drawing_card_feedback_lifecycle.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/drawing_card/sources
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardFeedbackLifecycle-2.2
  output: DrawingCardFeedbackLifecycle-2.3
acceptance_commands:
  - uv run --extra dev pytest -q tests/integration/test_drawing_card_feedback_lifecycle.py tests/integration/test_drawing_card_background_admin.py tests/unit/admin_panel/test_drawing_card_background_service.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/drawing_card_service.py tests/integration/test_drawing_card_feedback_lifecycle.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/drawing_card_service.py tests/integration/test_drawing_card_feedback_lifecycle.py
  - git diff --check
---

# Workbook review lifecycle

Store each uploaded review workbook under its next attempt directory. Stage and validate a unique
private `.xlsx`, then atomically replace the canonical attempt-scoped workbook so a retry can safely
supersede an orphan. A second fresh review generation must use the next attempt and run normally.
When `_run` enters `processing`, clear `job.review` from the durable processing manifest and include
it in the transition snapshot so an initial manifest failure restores the original retryable review
artifact. Add sequential-generation and failed-transition retry regressions; retain the shared apply
epoch and explicit inline feedback-before-rerun semantics.
