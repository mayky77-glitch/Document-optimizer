---
type: task
status: frozen
card_id: drawing-card-xlsb-openxml-limit
version: 1
supersedes: null
work_id: drawing-card-xlsb-openxml-limit-v1
task_id: xlsb-openxml-member-limit
purpose: Accept the verified real XLSB while retaining bounded OpenXML decompression safeguards.
role: developer
card_path: knowledge/tasks/drawing-card-xlsb-openxml-limit.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 73d7083f024f23c1d4e8b677487296c44631035c
branch: codex/drawing-card-xlsb-openxml-limit
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/sources/openxml_safety.py
  - tests/unit/drawing_card/test_source_schema_safety.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/admin_panel
  - tests/fixtures
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardOpenXmlSafety-1.0
  output: DrawingCardOpenXmlSafety-1.1
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/drawing_card/test_source_schema_safety.py tests/integration/test_drawing_card_admin.py
  - uv run --extra dev ruff check src/report_processor/drawing_card/sources/openxml_safety.py tests/unit/drawing_card/test_source_schema_safety.py
  - uv run --extra dev ruff format --check src/report_processor/drawing_card/sources/openxml_safety.py tests/unit/drawing_card/test_source_schema_safety.py
  - git diff --check
---

# Real XLSB OpenXML member limit

The verified real XLSB has 26 members, 291,722,776 total uncompressed bytes and a largest worksheet
member of 221,974,365 bytes at compression ratio 12.11. Raise only the per-member limit from 128 MiB
to 256 MiB. Retain the 512 MiB total, 4,096 member, ratio 100, safe-path and ZIP integrity limits.
Add exact boundary tests and do not add the user workbook to Git.
