---
type: task
status: frozen
card_id: drawing-card-release-test-fixtures
version: 1
supersedes: null
work_id: drawing-card-ux-release-test-fixtures-v3
task_id: valid-openxml-test-fixtures
purpose: Align test fixtures with strict OpenXML validation without weakening production safeguards.
role: developer
card_path: knowledge/tasks/drawing-card-release-test-fixtures.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 9927849c1f8737b7abeb4d0429488a620c2a566b
branch: codex/drawing-card-release-test-fixtures
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - tests/integration/test_hierarchy_workflows.py
  - tests/unit/drawing_card/test_drawing_card_service_contract.py
  - tests/unit/drawing_card/test_cable_coupling_family.py
  - tests/unit/drawing_card/test_xlsx_xml_precision.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardReleaseSafety-1.0
  output: DrawingCardReleaseTestFixtures-1.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/integration/test_hierarchy_workflows.py tests/unit/drawing_card/test_drawing_card_service_contract.py tests/unit/drawing_card/test_cable_coupling_family.py tests/unit/drawing_card/test_xlsx_xml_precision.py
  - uv run --extra dev ruff check tests/integration/test_hierarchy_workflows.py tests/unit/drawing_card/test_drawing_card_service_contract.py tests/unit/drawing_card/test_cable_coupling_family.py tests/unit/drawing_card/test_xlsx_xml_precision.py
  - uv run --extra dev ruff format --check tests/integration/test_hierarchy_workflows.py tests/unit/drawing_card/test_drawing_card_service_contract.py tests/unit/drawing_card/test_cable_coupling_family.py tests/unit/drawing_card/test_xlsx_xml_precision.py
  - git diff --check
---

# Valid OpenXML test fixtures

Replace obsolete four-byte ZIP stubs with the repository's valid safe workbook fixture so strict
OpenXML upload validation remains enabled. Apply formatting-only changes to the two files reported by
the full formatter. Do not change production behavior, fixture binaries, or user documents.
