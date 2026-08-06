---
type: task
status: frozen
card_id: drawing-card-ux-wave1-schema-safety
version: 1
supersedes: null
work_id: drawing-card-ux-wave1-v1
task_id: schema-safety
purpose: Implement semantic fail-closed schema recognition and comparable cumulative period extraction.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave1-schema-safety.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas: []
branch: codex/drawing-card-ux-wave1-schema-safety
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/sources/schema.py
  - src/report_processor/drawing_card/sources/extractor.py
  - src/report_processor/drawing_card/sources/inspection.py
  - src/report_processor/drawing_card/statuses.py
  - tests/unit/drawing_card/test_source_schema_safety.py
forbidden_paths:
  - src/report_processor/drawing_card/workflow.py
  - src/report_processor/drawing_card/models.py
  - src/report_processor/admin_panel
  - knowledge
  - docs
contract_versions:
  input: DrawingCardSourceHeaders-1.0
  output: DrawingCardSchemaRecognition-1.0+DrawingCardComparablePeriod-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/drawing_card/test_source_schema_safety.py tests/unit/drawing_card/test_hierarchy_aggregates.py
  - uv run ruff check src/report_processor/drawing_card/sources/schema.py src/report_processor/drawing_card/sources/extractor.py src/report_processor/drawing_card/sources/inspection.py src/report_processor/drawing_card/statuses.py tests/unit/drawing_card/test_source_schema_safety.py
  - git diff --check
---

# Schema safety

Implement the frozen schema contracts without changing matching categories, hierarchy filtering,
admin routes or UI. Preserve currently valid multi-row merged-header behavior.

Acceptance cases must include punctuation/case/line-break/`ё` variants, aliases, weak and tied
matches, conflicting physical roles, explicit residual-vs-intermediate blocks, and a cumulative
contract derived from whole-period performed plus explicit residual. Content-only position
evidence is diagnostic only and never authorizes hierarchy exclusion.

