---
type: task
status: frozen
card_id: drawing-card-source-layout-idempotency
version: 1
supersedes: null
work_id: drawing-card-ux-source-layout-idempotency-v1
task_id: source-layout-idempotency
purpose: Keep idempotent uploads exact across new ordinal directories and legacy flat source paths.
role: developer
card_path: knowledge/tasks/drawing-card-source-layout-idempotency.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 3d76f6ca657890bb132f5f5ac40c917d03fa8be4
branch: codex/drawing-card-source-layout-idempotency
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_service.py
  - tests/unit/admin_panel/test_drawing_card_service.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/drawing_card/sources
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardPrivateSourceLayout-2.0
  output: DrawingCardPrivateSourceLayout-2.1
acceptance_commands:
  - uv run --extra dev pytest -q tests/integration/test_drawing_card_background_admin.py tests/unit/admin_panel/test_drawing_card_background_service.py tests/unit/admin_panel/test_drawing_card_service.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/drawing_card_service.py tests/unit/admin_panel/test_drawing_card_service.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/drawing_card_service.py tests/unit/admin_panel/test_drawing_card_service.py
  - git diff --check
---

# Source-layout idempotency

Replace the old unconditional basename `partition("-")` logic with a bounded private-layout decoder.
New `sources/<ordinal>/<original-name>` paths compare by their unchanged basename; legacy
`sources/<ordinal>-<original-name>` manifests remain idempotent and readable. Arbitrary user names,
including names containing dashes or leading digits, remain exact. Add focused new/legacy path tests
and keep the existing background HTTP/service idempotency regressions green.
