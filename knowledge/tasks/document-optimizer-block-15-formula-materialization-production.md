---
type: task
card_id: document-optimizer-block-15-formula-materialization-production
status: done
version: 1
supersedes: document-optimizer-block-15-production
work_id: document-optimizer-block-15-formula-materialization
task_id: block-15-formula-production
purpose: "Пересчитать временную XLSX-копию и материализовать все формулы в конечные числа"
role: worker
agent_role: developer
owner: block-15-formula-production
profile: L2
routing_grade: P4
progress_revision: 3
state_fingerprint: "feature:6b621331b74dd983571da156b334c48736404364;integration:bcb514c6efc1804079b2d8e9531634a2c36da00b"
no_progress_count: 0
circuit_state: closed
routing_reason: "LibreOffice process isolation, OOXML formula materialization and atomic cleanup."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: "Persistent developer role uses configured medium effort."
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-15-formula-materialization-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - c8406336211bbabeee9953f6526ba5fde6f0de50
branch: codex/block-15-formula-materialization-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block15-formula-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/excel_writer/__init__.py
  - src/report_processor/excel_writer/engine.py
  - src/report_processor/excel_writer/formula_materialization.py
  - src/report_processor/excel_writer/models.py
  - src/report_processor/excel_writer/ooxml.py
source_paths:
  - src/report_processor/excel_writer
depends_on: []
forbidden_paths:
  - src/report_processor/excel_writer/exceptions.py
  - src/report_processor/cli.py
  - src/report_processor/__init__.py
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
  public_api: ExcelWriterEngine-15.1
  contract: ExcelWriterContract-15.1
  result_output: WriteResult-15.0
acceptance_commands:
  - "uv run --extra dev ruff check src/report_processor/excel_writer"
  - "uv run --extra dev ruff format --check src/report_processor/excel_writer"
  - "uv run python -m compileall -q src/report_processor/excel_writer"
tags:
  - task/implementation
  - status/done
  - layer/infrastructure
  - risk/high
---

# Block 15.1 production

Сохранить сигнатуру и поля `WriteResult`. Поднять версии contract/engine до
15.1. После разрешённых Decimal-изменений пересчитать только приватную временную
копию через `soffice` без shell и с отдельным profile. Оригинал не открывать на
запись.

Если формул нет, LibreOffice не запускать. Если формулы есть, не доверять
старому cache после изменения workbook. Материализовать каждую worksheet formula
в конечный числовой literal, сохранив style и остальные cell attributes. Удалить
устаревший `calcChain` metadata. Текст, blank, Excel error, non-finite value,
недоступность и timeout — controlled failure без output.

Финальная проверка: formula count zero; бывшие formula cells дают одинаковые
числа в formula/data-only views; source identity, no-clobber и temp cleanup
сохранены. Не добавлять CLI, dependency или конфигурационное выполнение.
