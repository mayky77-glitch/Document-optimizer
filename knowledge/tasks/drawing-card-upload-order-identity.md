---
type: task
status: frozen
card_id: drawing-card-upload-order-identity
version: 1
supersedes: null
work_id: drawing-card-ux-final-concurrency-scope-v1
task_id: upload-order-identity
purpose: Remove private storage ordinals from exact source identity while preserving logical members.
role: developer
card_path: knowledge/tasks/drawing-card-upload-order-identity.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - e5a23f17eb8448e14d9fdea2554fbb90f5169ad3
branch: codex/drawing-card-upload-order-identity
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/sources/manifest.py
  - tests/unit/drawing_card/test_source_manifest_identity.py
  - tests/unit/drawing_card/test_feedback_replay.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/admin_panel
  - src/report_processor/drawing_card/review/feedback.py
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardStableMemberIdentity-1.0
  output: DrawingCardStableMemberIdentity-1.1
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/drawing_card/test_source_manifest_identity.py tests/unit/drawing_card/test_feedback_replay.py
  - uv run --extra dev ruff check src/report_processor/drawing_card/sources/manifest.py tests/unit/drawing_card/test_source_manifest_identity.py tests/unit/drawing_card/test_feedback_replay.py
  - uv run --extra dev ruff format --check src/report_processor/drawing_card/sources/manifest.py tests/unit/drawing_card/test_source_manifest_identity.py tests/unit/drawing_card/test_feedback_replay.py
  - git diff --check
---

# Upload-order independent member identity

Private storage prefixes such as `01-` and `02-` must not participate in direct-file identity. Keep
content digest and the safe original logical name semantics, while directory/archive relative paths
remain distinct. Add a cross-job regression where the same two files are uploaded in reverse order
and produce identical row feedback contexts.
