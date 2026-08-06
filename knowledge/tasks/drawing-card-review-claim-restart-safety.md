---
type: task
status: frozen
card_id: drawing-card-review-claim-restart-safety
version: 1
supersedes: drawing-card-review-lock-project-multiset
work_id: drawing-card-ux-release-remediation-v1
task_id: review-claim-restart-safety
purpose: Consume each review generation once, roll back failed run transitions, and preserve exact restart scope.
role: developer
card_path: knowledge/tasks/drawing-card-review-claim-restart-safety.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - dc3f7cfe51af83e8279e92fe639df1318555185d
branch: codex/drawing-card-review-claim-restart-safety
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_service.py
  - tests/integration/test_drawing_card_feedback_lifecycle.py
  - tests/unit/admin_panel/test_drawing_card_service.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/drawing_card/sources/manifest.py
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardFeedbackLifecycle-2.1
  output: DrawingCardFeedbackLifecycle-2.2
acceptance_commands:
  - uv run --extra dev pytest -q tests/integration/test_drawing_card_feedback_lifecycle.py tests/unit/admin_panel/test_drawing_card_service.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/drawing_card_service.py tests/integration/test_drawing_card_feedback_lifecycle.py tests/unit/admin_panel/test_drawing_card_service.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/drawing_card_service.py tests/integration/test_drawing_card_feedback_lifecycle.py tests/unit/admin_panel/test_drawing_card_service.py
  - git diff --check
---

# Review claim and restart safety

Give workbook and inline apply one in-memory claim epoch so a queued request can never consume the
same review generation after the first rerun returns another review page. Preserve duplicate hashes
when restoring feedback scope. Roll back the pre-run in-memory transition if its first manifest save
fails while keeping already-confirmed feedback durable and immediately retryable. Store new service
uploads under ordinal subdirectories with their original safe basename unchanged; old manifests stay
readable. Add both path-order concurrency tests with a `review_required` first result, a fail-on-second
save retry test, restart multiplicity coverage, and a storage-layout assertion.
