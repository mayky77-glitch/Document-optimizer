---
type: task
card_id: document-optimizer-block-08-tests
status: frozen
version: 1
supersedes: null
work_id: document-optimizer-block-08
task_id: block-08-tests
purpose: "Доказать contract 7→8, детерминизм, provenance и безопасные dictionaries"
role: tester
owner: block-08-tests
routing_grade: P3
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
card_path: knowledge/tasks/document-optimizer-block-08-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 4e4279f113cd96128c3335c3ca04e765ea833370
branch: codex/block-08-normalization-tests
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/normalization
  - tests/contract/test_block7_to_block8_contract.py
  - tests/integration/test_normalize_rows_cli.py
forbidden_paths:
  - src
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
contract_versions:
  input: TrainingDataRow-7.0
  output: NormalizedSourceRow-8.0
acceptance_commands:
  - "uv run pytest tests/unit/normalization tests/contract/test_block7_to_block8_contract.py tests/integration/test_normalize_rows_cli.py"
  - "uv run ruff check tests/unit/normalization tests/contract/test_block7_to_block8_contract.py tests/integration/test_normalize_rows_cli.py"
tags:
  - task/implementation
  - status/in-progress
  - layer/backend
  - risk/high
---

# Block 8 tests

Проверить: сохранение всех строк, raw/provenance/Decimal, ведущие нули, Unicode,
единицы, токены, exact typo map, одинаковый business `line_id` при разных
source files, разные ID при разных ключах, collision evidence и JSONL/CLI.
