---
type: task
status: frozen
card_id: drawing-card-release-feedback-integrity
version: 1
supersedes: null
work_id: drawing-card-ux-release-remediation-v1
task_id: feedback-ledger-integrity
purpose: Keep the durable feedback ledger readable at its bounds and invalidate only the intended event.
role: developer
card_path: knowledge/tasks/drawing-card-release-feedback-integrity.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 8493f5fa712364b8ffd629cf695fc878c2715008
branch: codex/drawing-card-release-feedback-integrity
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/review/feedback.py
  - tests/unit/drawing_card/test_feedback_store.py
  - tests/unit/drawing_card/test_feedback_replay.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/drawing_card/sources
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardFeedback-2.0
  output: DrawingCardFeedback-2.1
acceptance_commands:
  - uv run pytest -q tests/unit/drawing_card/test_feedback_store.py tests/unit/drawing_card/test_feedback_replay.py
  - uv run ruff check src/report_processor/drawing_card/review/feedback.py tests/unit/drawing_card/test_feedback_store.py tests/unit/drawing_card/test_feedback_replay.py
  - uv run ruff format --check src/report_processor/drawing_card/review/feedback.py tests/unit/drawing_card/test_feedback_store.py tests/unit/drawing_card/test_feedback_replay.py
  - git diff --check
---

# Release feedback ledger integrity

Under the existing inter-process ledger lock, reject any append whose prospective complete ledger
would exceed the same maximum entry count or serialized byte limit enforced by reads. The existing
ledger must remain byte-for-byte intact on rejection; a valid write must never make the next lookup
fail its own bounded-read contract. Add exact boundary and rollback tests.

Invalidation must supersede only its declared target event. When an older decision is invalidated
after a newer valid decision exists in the same exact context, lookup must return the newest valid,
unsuperseded event. Preserve exact tenant/project/context/version/hazard matching and add regression
tests for old event → newer event → invalidation of old event, plus invalidation of the current event.
