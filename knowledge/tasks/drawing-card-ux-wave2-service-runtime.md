---
type: task
status: frozen
card_id: drawing-card-ux-wave2-service-runtime
version: 1
supersedes: null
work_id: drawing-card-ux-wave2-v1
task_id: service-runtime
purpose: Integrate background execution, persisted recovery, isolated attempts, idempotency, cancellation and retry into DrawingCardService.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave2-service-runtime.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - f23945d6e8214697d8f198292bae1a07239c5e62
branch: codex/drawing-card-ux-wave2-service-runtime
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_service.py
  - tests/unit/admin_panel/test_drawing_card_background_service.py
  - tests/unit/admin_panel/test_drawing_card_service.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/drawing_card
  - knowledge
  - docs
contract_versions:
  input: DrawingCardLifecycle-1.0+DrawingCardPrivateManifestStore-1.0
  output: DrawingCardBackgroundService-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/admin_panel/test_drawing_card_service.py tests/unit/admin_panel/test_drawing_card_background_service.py
  - uv run ruff check src/report_processor/admin_panel/drawing_card_service.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/admin_panel/test_drawing_card_background_service.py
  - git diff --check
---

# Service runtime

Preserve direct-service compatibility: existing callers remain synchronous by default, while an
explicit `background=True` mode returns immediately and is what the production app will select.
Use daemon worker threads with bounded concurrency or another shutdown-safe local mechanism.

Required additive job fields: phase, processed/total files, processed/total rows, UTC
started/updated timestamps, controlled terminal cause, monotonic attempt, idempotency key and a
cooperative cancellation event that is never serialized.

Requirements:

- persist initial upload state before scheduling work;
- isolate each run under `attempts/NNNN`, publish only the validated current attempt;
- duplicate create with the same validated idempotency key returns the same job and never runs a
  second worker;
- cancellation is valid only for queued/processing jobs, requests cooperative workflow stop,
  removes partial current-attempt output and ends as `cancelled`;
- retry is valid for cancelled/failed/blocked jobs, increments attempt and clears only public
  terminal/result fields without deleting old private audit artifacts;
- restore valid manifests, ready results and accepted inline decisions; schedule previously active
  jobs in background mode from retained private sources, without re-upload;
- persist review item/cluster/bulk/undo decisions before returning from every mutation;
- append durable feedback only after a successful validated rerun, preserving current behavior;
- reject changed source hashes and unsafe/symlinked restored paths; never serialize absolute paths,
  source values or uncontrolled exception strings.

Do not add routes, public payload fields, UI polling or change extraction/matching/review semantics.
