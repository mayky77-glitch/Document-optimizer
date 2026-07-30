---
type: task
card_id: document-optimizer-block-08-production
status: frozen
version: 1
supersedes: null
work_id: document-optimizer-block-08
task_id: block-08-production
purpose: "Реализовать NormalizedSourceRow, business key, tokens, dictionaries и line_id"
role: developer
owner: block-08-production
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
card_path: knowledge/tasks/document-optimizer-block-08-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 4e4279f113cd96128c3335c3ca04e765ea833370
branch: codex/block-08-normalization-production
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/normalization
forbidden_paths:
  - src/report_processor/cli.py
  - src/report_processor/cli_normalization.py
  - src/report_processor/training_data
  - src/report_processor/storage
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
contract_versions:
  input: TrainingDataRow-7.0
  output: NormalizedSourceRow-8.0
acceptance_commands:
  - "uv run ruff check src/report_processor/normalization"
  - "uv run pytest tests/unit/normalization tests/contract/test_block7_to_block8_contract.py"
tags:
  - task/implementation
  - status/in-progress
  - layer/backend
  - risk/high
---

# Block 8 production

Публичный пакет принимает каждую строку блока 7 и ничего не удаляет. Сохраняет
provenance и исходную строку. Формирует normalized codes/name/unit, стабильные
tokens, `NormalizedBusinessKey` и `line_id`, не зависящий от физического файла.
Опечатки исправляет только точным словарём данных; код из конфигурации не
исполняет. Денежные значения остаются `Decimal`.
