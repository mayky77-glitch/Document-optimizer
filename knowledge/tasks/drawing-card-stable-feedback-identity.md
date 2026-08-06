---
type: task
status: frozen
card_id: drawing-card-stable-feedback-identity
version: 1
supersedes: null
work_id: drawing-card-ux-release-hardening-v1
task_id: stable-feedback-identity
purpose: Make exact safe feedback replay stable across independent jobs for identical source content.
role: developer
card_path: knowledge/tasks/drawing-card-stable-feedback-identity.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - c2db262f687a2f3eb7a1351de5525a04b8bd1405
branch: codex/drawing-card-stable-feedback-identity
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/sources/manifest.py
  - tests/unit/drawing_card/test_feedback_replay.py
  - tests/unit/drawing_card/test_source_manifest_identity.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/admin_panel
  - src/report_processor/drawing_card/review/feedback.py
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardExactFeedback-2.0
  output: DrawingCardStableMemberIdentity-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/drawing_card/test_feedback_replay.py tests/unit/drawing_card/test_source_manifest_identity.py
  - uv run --extra dev ruff check src/report_processor/drawing_card/sources/manifest.py tests/unit/drawing_card/test_feedback_replay.py tests/unit/drawing_card/test_source_manifest_identity.py
  - uv run --extra dev ruff format --check src/report_processor/drawing_card/sources/manifest.py tests/unit/drawing_card/test_feedback_replay.py tests/unit/drawing_card/test_source_manifest_identity.py
  - git diff --check
---

# Stable exact feedback identity

Remove absolute/random job paths from source member identity. Use bounded content-derived identity plus
safe logical workbook coordinates so the same source content in two independent private job folders
produces the same row/member identity. Preserve distinct members inside directories/archives, tenant
and project isolation, input hashes, contract position, category, unit, match mode, rule versions and
hazard fail-closed behavior. Add a cross-job regression test.
