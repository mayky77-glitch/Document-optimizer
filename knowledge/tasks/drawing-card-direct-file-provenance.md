---
type: task
status: frozen
card_id: drawing-card-direct-file-provenance
version: 1
supersedes: drawing-card-upload-order-identity
work_id: drawing-card-ux-release-remediation-v1
task_id: direct-file-provenance
purpose: Preserve every arbitrary direct filename and rely only on explicit service storage provenance.
role: developer
card_path: knowledge/tasks/drawing-card-direct-file-provenance.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - dc3f7cfe51af83e8279e92fe639df1318555185d
branch: codex/drawing-card-direct-file-provenance
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/sources/manifest.py
  - tests/unit/drawing_card/test_feedback_replay.py
  - tests/unit/drawing_card/test_source_manifest_identity.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/admin_panel
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardStableMemberIdentity-1.1
  output: DrawingCardStableMemberIdentity-1.2
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/drawing_card/test_source_manifest_identity.py tests/unit/drawing_card/test_feedback_replay.py
  - uv run --extra dev ruff check src/report_processor/drawing_card/sources/manifest.py tests/unit/drawing_card/test_source_manifest_identity.py tests/unit/drawing_card/test_feedback_replay.py
  - uv run --extra dev ruff format --check src/report_processor/drawing_card/sources/manifest.py tests/unit/drawing_card/test_source_manifest_identity.py tests/unit/drawing_card/test_feedback_replay.py
  - git diff --check
---

# Direct-file provenance

Remove numeric-prefix inference from public direct-file scanning. Every arbitrary filename, including
`2026-report.xlsx` and `01-report.xlsx`, remains an exact semantic identity component and cannot be
silently deduplicated with another name. Reverse-order stability comes from the service-owned ordinal
subdirectory while `scan_file` sees the unchanged original basename. Directory and archive identities
remain unchanged. Add manifest-cardinality and cross-job exact-feedback replay regressions.
