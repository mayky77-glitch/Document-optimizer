---
type: task
status: frozen
card_id: drawing-card-review-lock-project-multiset
version: 1
supersedes: null
work_id: drawing-card-ux-final-concurrency-scope-v1
task_id: review-lock-project-multiset
purpose: Serialize both review application paths and preserve input multiplicity in feedback scope.
role: developer
card_path: knowledge/tasks/drawing-card-review-lock-project-multiset.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - e5a23f17eb8448e14d9fdea2554fbb90f5169ad3
branch: codex/drawing-card-review-lock-project-multiset
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/drawing_card/review/feedback.py
  - tests/integration/test_drawing_card_feedback_lifecycle.py
  - tests/unit/admin_panel/test_drawing_card_service.py
  - tests/unit/drawing_card/test_feedback_store.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/drawing_card/sources
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardFeedbackLifecycle-2.0
  output: DrawingCardFeedbackLifecycle-2.1
acceptance_commands:
  - uv run --extra dev pytest -q tests/integration/test_drawing_card_feedback_lifecycle.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_feedback_store.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/drawing_card_service.py src/report_processor/drawing_card/review/feedback.py tests/integration/test_drawing_card_feedback_lifecycle.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_feedback_store.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/drawing_card_service.py src/report_processor/drawing_card/review/feedback.py tests/integration/test_drawing_card_feedback_lifecycle.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_feedback_store.py
  - git diff --check
---

# Review lock and project multiset

Use the same per-job lock for completed-workbook review upload and inline page application so only one
rerun can start. Preserve the sorted multiset of source/existing hashes, including multiplicity, in
project ID and feedback audit context. Keep the explicit user contract: a confirmed inline feedback
page remains durably saved before rerun and is not rolled back if rerun fails. Add deterministic
cross-path concurrency and one-vs-two-identical-input negative replay tests.
