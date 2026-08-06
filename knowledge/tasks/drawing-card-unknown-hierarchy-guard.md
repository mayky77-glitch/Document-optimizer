---
type: task
status: frozen
card_id: drawing-card-unknown-hierarchy-guard
version: 1
supersedes: null
work_id: drawing-card-ux-release-hardening-v1
task_id: unknown-hierarchy-guard
purpose: Prevent silent publication when a position hierarchy is inferred only from content.
role: developer
card_path: knowledge/tasks/drawing-card-unknown-hierarchy-guard.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - c2db262f687a2f3eb7a1351de5525a04b8bd1405
branch: codex/drawing-card-unknown-hierarchy-guard
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/sources/schema.py
  - tests/unit/drawing_card/test_source_schema_safety.py
  - tests/integration/test_hierarchy_workflows.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/admin_panel
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardSchemaRecognition-2.0
  output: DrawingCardUnknownHierarchyGuard-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/drawing_card/test_source_schema_safety.py tests/integration/test_hierarchy_workflows.py
  - uv run --extra dev ruff check src/report_processor/drawing_card/sources/schema.py tests/unit/drawing_card/test_source_schema_safety.py tests/integration/test_hierarchy_workflows.py
  - uv run --extra dev ruff format --check src/report_processor/drawing_card/sources/schema.py tests/unit/drawing_card/test_source_schema_safety.py tests/integration/test_hierarchy_workflows.py
  - git diff --check
---

# Unknown hierarchy guard

Content-only position-column evidence is diagnostic, never an authorization to classify parent rows.
Mark the schema uncertain (`AMBIGUOUS_SCHEMA`) and ensure it cannot be selected for extraction or
publication until an explicit header/policy exists. Keep current four real sources recognized and add
tests proving the unknown hierarchy is visible and fail-closed.
