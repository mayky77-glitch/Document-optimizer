---
type: task
card_id: document-optimizer-block-15-tests
status: done
version: 1
supersedes: null
work_id: document-optimizer-block-15
task_id: block-15-tests
purpose: "Доказать атомарность, preservation и real-XLSX безопасность блока 15"
role: worker
agent_role: tester
owner: block-15-tests
profile: L1
routing_grade: P3
progress_revision: 3
state_fingerprint: "feature:fcdef7c659e43f119cafbfc168bbb66cea744a1e;integration:3f1bdba2662803717d7113dde94d723cc582ded0"
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent contract, fail-injection, preservation and real-XLSX verification."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-15-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 2edf6235462c3d1cfab0b31923a04069c98c12e1
branch: codex/block-15-excel-writer-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block15-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/excel_writer
  - tests/fixtures/excel_writer
  - tests/contract/test_block15_excel_writer_contract.py
  - tests/integration/test_block15_excel_writer.py
  - tests/integration/test_block15_real_data.py
source_paths:
  - tests/unit/excel_writer
  - tests/fixtures/excel_writer
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
  public_api: ExcelWriterEngine-15.0
  contract: ExcelWriterContract-15.0
acceptance_commands:
  - "uv run --extra dev ruff check tests/unit/excel_writer tests/fixtures/excel_writer tests/contract/test_block15_excel_writer_contract.py tests/integration/test_block15_excel_writer.py tests/integration/test_block15_real_data.py"
  - "uv run --extra dev ruff format --check tests/unit/excel_writer tests/fixtures/excel_writer tests/contract/test_block15_excel_writer_contract.py tests/integration/test_block15_excel_writer.py tests/integration/test_block15_real_data.py"
  - "uv run --extra dev pytest -q tests/unit/excel_writer tests/contract/test_block15_excel_writer_contract.py tests/integration/test_block15_excel_writer.py"
  - "DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX='/Users/x/Documents/Сооотношение документов/15-31/0784 согл окз/0784_КС-2_КС-3_КС-6а июль 2026 ч.2.xlsx' DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX='/Users/x/Documents/Сооотношение документов/пример нюанс 1/1ДОПОТЧЕТ  ИЮЛЬ_ИТОГ.xlsx' RUN_SLOW=1 uv run --extra dev pytest -q tests/integration/test_block15_real_data.py"
tags:
  - task/implementation
  - status/done
  - layer/test
  - risk/high
---

# Block 15 tests

Только test/fixture scope. Покрыть четыре decisions, две разрешённые колонки,
quantity-only/cost-only, `None`, Decimal scale/sign, reverse-order stability,
duplicates, identity/raw-lexeme drift, formula/merged target rejection,
unsupported package и output no-clobber.

Golden/preservation checks: package entries, unchanged parts, formulas и cached
lexemes, styles/number formats, comments, merged ranges, filters, panes,
dimensions и sheet metadata. Failure injection для temp write, verify, reopen и
publish обязана оставлять source и existing output неизменными.

Real-data test получает пути только через environment. Полный pipeline должен
вернуть `REQUIRE_MANUAL_REVIEW` и не создать output. Единственный matched subset
должен вернуть `ALLOW_WRITE`, создать только временный XLSX и изменить ровно
`Лист!D30` на Decimal `0`. Проверить повторное открытие, 14 формул, 128 merged
ranges, package structure и неизменность SHA-256/size/mtime обоих originals.
Generated workbook не коммитить.
