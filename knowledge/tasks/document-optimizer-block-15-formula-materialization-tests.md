---
type: task
card_id: document-optimizer-block-15-formula-materialization-tests
status: claimed
version: 1
supersedes: document-optimizer-block-15-tests
work_id: document-optimizer-block-15-formula-materialization
task_id: block-15-formula-tests
purpose: "Доказать numeric-only output, fallback-пересчёт и безопасность реальных XLSX"
role: worker
agent_role: tester
owner: block-15-formula-tests
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent contract, LibreOffice failure injection and real-XLSX verification."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-15-formula-materialization-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - c8406336211bbabeee9953f6526ba5fde6f0de50
branch: codex/block-15-formula-materialization-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block15-formula-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/excel_writer/test_formula_materialization.py
  - tests/unit/excel_writer/test_ooxml.py
  - tests/contract/test_block15_excel_writer_contract.py
  - tests/integration/test_block15_excel_writer.py
  - tests/integration/test_block15_real_data.py
source_paths:
  - tests/unit/excel_writer
  - tests/contract/test_block15_excel_writer_contract.py
  - tests/integration/test_block15_excel_writer.py
  - tests/integration/test_block15_real_data.py
depends_on: []
forbidden_paths:
  - src
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - .github
  - knowledge
  - .codex
  - tests/conftest.py
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  public_api: ExcelWriterEngine-15.1
  contract: ExcelWriterContract-15.1
acceptance_commands:
  - "uv run --extra dev ruff check tests/unit/excel_writer tests/contract/test_block15_excel_writer_contract.py tests/integration/test_block15_excel_writer.py tests/integration/test_block15_real_data.py"
  - "uv run --extra dev ruff format --check tests/unit/excel_writer tests/contract/test_block15_excel_writer_contract.py tests/integration/test_block15_excel_writer.py tests/integration/test_block15_real_data.py"
  - "uv run --extra dev pytest -q tests/unit/excel_writer tests/contract/test_block15_excel_writer_contract.py tests/integration/test_block15_excel_writer.py"
  - "DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX='/Users/x/Documents/Сооотношение документов/15-31/0784 согл окз/0784_КС-2_КС-3_КС-6а июль 2026 ч.2.xlsx' DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX='/Users/x/Documents/Сооотношение документов/пример нюанс 1/1ДОПОТЧЕТ  ИЮЛЬ_ИТОГ.xlsx' RUN_SLOW=1 uv run --extra dev pytest -q tests/integration/test_block15_real_data.py"
tags:
  - task/implementation
  - status/claimed
  - layer/test
  - risk/high
---

# Block 15.1 tests

Только test scope. Покрыть workbook без формул; cached, missing-cache и stale-cache
формулы; зависимость формулы от изменённой target cell; shared formulas; text,
blank, Excel error и non-finite результаты; missing executable, timeout и
process failure; skip decisions; existing output; temp cleanup; source identity.

Проверять zero `<f>` во всех worksheets, numeric literals, одинаковое чтение
formula/data-only views, сохранение styles и merges. Real target: D30 равен 0,
14 формул превращены в 14 чисел, formula count 0, merged ranges 128, SHA-256,
size и mtime обоих originals неизменны. Generated XLSX не коммитить.
