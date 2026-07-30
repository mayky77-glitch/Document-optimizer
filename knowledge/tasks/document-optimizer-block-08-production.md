---
type: task
card_id: document-optimizer-block-08-production
status: done
version: 1
supersedes: null
work_id: document-optimizer-block-08
task_id: block-08-production
purpose: "Реализовать NormalizedSourceRow, business key, tokens, dictionaries и line_id"
role: worker
agent_role: developer
owner: block-08-production
profile: L1
routing_grade: P3
progress_revision: 2
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Normal implementation after shared block-8 contract was frozen."
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
card_path: knowledge/tasks/document-optimizer-block-08-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 4e4279f113cd96128c3335c3ca04e765ea833370
branch: codex/block-08-normalization-production
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/normalization
source_paths:
  - src/report_processor/normalization
depends_on: []
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
  - status/done
  - layer/backend
  - risk/high
---

# Block 8 production

Публичный пакет принимает каждую строку блока 7 и ничего не удаляет. Сохраняет
provenance и исходную строку. Формирует normalized codes/name/unit, стабильные
tokens, `NormalizedBusinessKey` и `line_id`, не зависящий от физического файла.
Опечатки исправляет только точным словарём данных; код из конфигурации не
исполняет. Денежные значения остаются `Decimal`.
