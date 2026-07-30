---
type: task
card_id: document-optimizer-block-15-production
status: claimed
version: 1
supersedes: null
work_id: document-optimizer-block-15
task_id: block-15-production
purpose: "Реализовать атомарный no-clobber XLSX writer с точечным OOXML изменением"
role: worker
agent_role: developer
owner: block-15-production
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Difficult OOXML preservation, Decimal serialization and atomic filesystem publication."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-15-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 2edf6235462c3d1cfab0b31923a04069c98c12e1
branch: codex/block-15-excel-writer-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block15-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/excel_writer
source_paths:
  - src/report_processor/excel_writer
depends_on: []
forbidden_paths:
  - src/report_processor/__init__.py
  - src/report_processor/cli.py
  - src/report_processor/target_report
  - src/report_processor/calculation
  - src/report_processor/quality_control
  - src/report_processor/matching
  - src/report_processor/business_rules
  - src/report_processor/analytics
  - src/report_processor/storage
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - .github
  - knowledge
  - .codex
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  public_api: ExcelWriterEngine-15.0
  contract: ExcelWriterContract-15.0
  target_input: TargetReport-9.0
  calculation_input: CalculationContract-13.0
  decision_input: QualityControlContract-14.0
  result_output: WriteResult-15.0
acceptance_commands:
  - "uv run --extra dev ruff check src/report_processor/excel_writer"
  - "uv run --extra dev ruff format --check src/report_processor/excel_writer"
  - "uv run python -m compileall -q src/report_processor/excel_writer"
tags:
  - task/implementation
  - status/claimed
  - layer/infrastructure
  - risk/high
---

# Block 15 production

Создать отдельный `report_processor.excel_writer` и frozen API
`write_target_report(source_path, output_path, decision, calculation_results, target_schema)`.

Запись разрешена только для `ALLOW_WRITE` и `ALLOW_WRITE_WITH_WARNINGS`.
`REQUIRE_MANUAL_REVIEW` и `BLOCK_WRITE` возвращают `SKIPPED_DECISION`, не
создают output и не меняют существующий файл. Writer не пересчитывает matching,
quality, totals, coefficient, rounding или формулы.

Разрешены только `quantity -> CURRENT_PERIOD_QUANTITY` и
`cost -> CURRENT_PERIOD_COST` для calculated results. `None` не очищает ячейку.
Требуются точные schema binding, writable row, coordinate/row/raw-lexeme
identity, существующий style; formula и merged targets запрещены. Значения —
только конечный `Decimal`, сериализация `format(value, "f")`, без float.

Использовать точечную OOXML-модификацию. Все package parts вне затронутого
worksheet byte-identical; формулы, cached lexemes, styles, comments, merges,
relationships и structure неизменны. Только `.xlsx`; `.xlsm` и signed package
отклоняются.

Публиковать через temp в output directory, полную проверку, `fsync`, повторную
проверку source и atomic hard-link no-clobber. При любой ошибке удалить temp;
source и существующий output не трогать. Не добавлять CLI и wiring.
