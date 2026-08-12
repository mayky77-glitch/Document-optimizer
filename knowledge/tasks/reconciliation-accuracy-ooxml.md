---
type: task
status: draft
card_id: reconciliation-accuracy-ooxml
version: 1
work_id: reconciliation-max-accuracy-specialists-v1
task_id: xlsx-publication
purpose: Audit XLSX transformation, formula materialization and atomic publication integrity.
role: worker
agent_role: debugger
owner: xlsx-publication
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
source_base_sha_source: exact planning commit supplied in launch envelope
branch: codex/reconciliation-accuracy-ooxml
branch_base_sha_source: exact planning commit supplied in launch envelope
write_scope: []
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - "**/*.xlsx"
contract_versions:
  input: ReconciliationWriterBoundary-1.0
  output: ReconciliationXlsxAudit-1.0
acceptance_commands:
  - uv run pytest -q tests/contract/test_block15_excel_writer_contract.py tests/integration/test_block15_excel_writer.py tests/unit/excel_writer
tags:
  - task/review
  - status/draft
  - domain/document-processing
  - capability/xlsx-output
  - risk/high
---

# XLSX publication audit

Read-only audit of bound-cell writes, RUB scaling, two-decimal values, formula materialization,
OOXML/VBA/relationship preservation, no-clobber behavior and unchanged byte-identical output.
Return an OOXML delta allowlist, digest/reopen results and package-level reproductions for any
unexpected mutation or cleanup failure.
