---
type: task
status: frozen
card_id: drawing-card-restart-log-persistence
version: 1
supersedes: null
work_id: drawing-card-ux-release-hardening-v1
task_id: restart-log-persistence
purpose: Preserve the bounded simple review log and funnel audit across service restarts.
role: developer
card_path: knowledge/tasks/drawing-card-restart-log-persistence.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - c2db262f687a2f3eb7a1351de5525a04b8bd1405
branch: codex/drawing-card-restart-log-persistence
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_service.py
  - tests/unit/admin_panel/test_drawing_card_job_store.py
  - tests/unit/admin_panel/test_drawing_card_service.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/admin_panel/assets
  - src/report_processor/drawing_card/sources
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardPrivateJobManifest-2.0
  output: DrawingCardRestartLogPersistence-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_drawing_card_job_store.py tests/unit/admin_panel/test_drawing_card_service.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/drawing_card_service.py tests/unit/admin_panel/test_drawing_card_job_store.py tests/unit/admin_panel/test_drawing_card_service.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/drawing_card_service.py tests/unit/admin_panel/test_drawing_card_job_store.py tests/unit/admin_panel/test_drawing_card_service.py
  - git diff --check
---

# Restart-safe simple log

Persist and restore only the bounded path-free schema recognition entries, disposition counts and
strict blocker codes already exposed to the user. Keep the UI/report model as a simple log list with
reason/source context; do not introduce a separate complex error subsystem. Reject or safely prune
unbounded/nested arbitrary manifest content and add restart regression tests.
