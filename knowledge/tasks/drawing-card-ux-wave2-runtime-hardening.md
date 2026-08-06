---
type: task
status: frozen
card_id: drawing-card-ux-wave2-runtime-hardening
version: 1
supersedes: drawing-card-ux-wave2-service-runtime
work_id: drawing-card-ux-wave2-remediation-v1
task_id: runtime-hardening
purpose: Close the independent review findings in drawing-card recovery, cancellation, input integrity, retry atomicity and retention.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave2-runtime-hardening.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 4afa647de751023b4f67dce82d1e06e87ba9d978
branch: codex/drawing-card-ux-wave2-runtime-hardening
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_job_store.py
  - src/report_processor/drawing_card/workflow.py
  - tests/unit/admin_panel/test_drawing_card_service.py
  - tests/unit/admin_panel/test_drawing_card_background_service.py
  - tests/unit/admin_panel/test_drawing_card_job_store.py
  - tests/unit/drawing_card/test_workflow_lifecycle.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/assets
  - knowledge
  - docs
contract_versions:
  input: DrawingCardBackgroundService-1.0
  output: DrawingCardBackgroundService-1.1
acceptance_commands:
  - uv run pytest -q tests/unit/admin_panel/test_drawing_card_service.py tests/unit/admin_panel/test_drawing_card_background_service.py tests/unit/admin_panel/test_drawing_card_job_store.py tests/unit/drawing_card/test_workflow_lifecycle.py
  - uv run ruff check src/report_processor/admin_panel/drawing_card_service.py src/report_processor/admin_panel/drawing_card_job_store.py src/report_processor/drawing_card/workflow.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/admin_panel/test_drawing_card_background_service.py tests/unit/admin_panel/test_drawing_card_job_store.py tests/unit/drawing_card/test_workflow_lifecycle.py
  - git diff --check
---

# Runtime hardening

Resolve all server-side findings from the Wave 2 independent review:

- restore a ready result only when it is the canonical, non-symlinked validated result of the
  current attempt; a hostile manifest must never publish a source or an older attempt;
- honor cancellation after validation and again immediately after the runner returns, before any
  result or review artifact becomes public;
- persist and verify the update-mode existing-card SHA-256 before each attempt, after workflow
  completion and during restore;
- make retry state mutation rollback completely when manifest persistence fails, and schedule work
  only after the new state is durably committed;
- make retention durable and internally consistent: active/review jobs survive restoration,
  cancelled is terminal, stale idempotency mappings cannot remain, and bounded terminal manifests
  cannot displace active work.

Keep source paths private, preserve old attempt audit artifacts, and add hostile-manifest,
cancel-during-validation, update-card-tamper, persistence-fault and bounded-retention tests.
