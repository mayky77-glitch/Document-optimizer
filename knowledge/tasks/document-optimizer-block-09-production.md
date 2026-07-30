---
type: task
card_id: document-optimizer-block-09-production
status: done
version: 1
supersedes: null
work_id: document-optimizer-blocks-09-10
task_id: block-09-production
purpose: "Безопасно прочитать целевой Excel и построить immutable TargetReportSchema/Row"
role: worker
agent_role: developer
owner: block-09-production
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded target-report package implementation with frozen immutable contract."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
card_path: knowledge/tasks/document-optimizer-block-09-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - c04008c51d39996788b0bcb9d6465e280d01938c
branch: codex/block-09-target-report-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block09-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/target_report
source_paths:
  - src/report_processor/target_report
depends_on: []
forbidden_paths:
  - src/report_processor/business_rules
  - src/report_processor/cli.py
  - src/report_processor/cli_target_report.py
  - src/report_processor/__init__.py
  - src/report_processor/storage
  - src/report_processor/normalization
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  input: "target-xlsx + WorkbookSchema@c04008c"
  output: "TargetReportRow-9.0 + TargetReportSchema-9.0"
  serialization: target-report-json-9.0
acceptance_commands:
  - "uv run ruff check src/report_processor/target_report"
  - "uv run pytest tests/unit/target_report tests/contract/test_block5_to_block9_contract.py tests/integration/test_target_report_immutability.py"
tags:
  - task/implementation
  - status/done
  - layer/backend
  - risk/high
---

# Block 9 production

Только read-only чтение `DualWorkbookSession` и OOXML. Исходник не
сохранять и не менять. Сохранить raw formulas, cache state, styles, merged
ranges, filters, comments, dimensions, source fingerprint и finite `Decimal`.
Неоднозначные period pairs и columns требуют override; не угадывать.
Package публикует immutable `TargetReportRow`, `TargetReportSchema`,
`TargetReportReadRequest`, diagnostics и future-write plans без mutation.
