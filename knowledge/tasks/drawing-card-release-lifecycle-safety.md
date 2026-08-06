---
type: task
status: frozen
card_id: drawing-card-release-lifecycle-safety
version: 1
supersedes: null
work_id: drawing-card-ux-release-remediation-v1
task_id: lifecycle-atomicity-openxml
purpose: Close release-blocking review concurrency, unsafe bulk-action, and OpenXML decompression hazards.
role: developer
card_path: knowledge/tasks/drawing-card-release-lifecycle-safety.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 8493f5fa712364b8ffd629cf695fc878c2715008
branch: codex/drawing-card-release-lifecycle-safety
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/drawing_card/sources/readers.py
  - src/report_processor/drawing_card/sources/openxml_safety.py
  - tests/integration/test_drawing_card_admin.py
  - tests/integration/test_drawing_card_feedback_lifecycle.py
  - tests/integration/test_drawing_card_review_api.py
  - tests/unit/admin_panel/test_drawing_card_service.py
  - tests/unit/drawing_card/test_source_schema_safety.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/drawing_card/review/feedback.py
  - tests/unit/drawing_card/test_feedback_store.py
  - tests/unit/drawing_card/test_feedback_replay.py
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardReviewServiceCore-3.0
  output: DrawingCardReleaseLifecycleSafety-1.0
acceptance_commands:
  - uv run pytest -q tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_feedback_lifecycle.py tests/integration/test_drawing_card_review_api.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_source_schema_safety.py
  - uv run ruff check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/drawing_card_service.py src/report_processor/drawing_card/sources/readers.py src/report_processor/drawing_card/sources/openxml_safety.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_feedback_lifecycle.py tests/integration/test_drawing_card_review_api.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_source_schema_safety.py
  - uv run ruff format --check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/drawing_card_service.py src/report_processor/drawing_card/sources/readers.py src/report_processor/drawing_card/sources/openxml_safety.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_feedback_lifecycle.py tests/integration/test_drawing_card_review_api.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_source_schema_safety.py
  - git diff --check
---

# Release lifecycle and OpenXML safety

Remove or strictly constrain cross-cluster bulk review so no request can bypass current packet
version, packet eligibility, hazard, category, unit, match-mode, tenant or project boundaries.
Preserve safe per-packet UI/API decisions; reject legacy global approve/reject semantics.

Serialize review mutations and final application per job. Two concurrent apply requests must not
both run. A failed rerun or failed durable manifest commit must not leave feedback eligible for
future replay. Use an explicit committed generation/two-phase protocol and keep the whole page
decision atomic: either the complete page becomes committed and replayable with the successful
rerun, or neither page feedback nor final state is visible. Add deterministic concurrency and
failure-injection tests.

Before any OpenXML member is decompressed, reject unsafe workbook containers using central limits:
safe relative member paths, bounded member count, per-member and total uncompressed sizes, and a
bounded compression ratio. Apply the same preflight to upload validation and the OpenXML reader.
Keep existing 256 MiB request limits and valid XLSX/XLSM/XLSB behavior.
