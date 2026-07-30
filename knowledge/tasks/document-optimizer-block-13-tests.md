---
type: task
card_id: document-optimizer-block-13-tests
status: done
version: 1
supersedes: null
work_id: document-optimizer-block-13
task_id: block-13-tests
purpose: "Доказать Decimal формулы, правила, trace и real-data безопасность блока 13"
role: worker
agent_role: tester
owner: block-13-tests
profile: L1
routing_grade: P3
progress_revision: 5
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent contract, numeric, deterministic and real-XLSX verification."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: "Fresh higher-route worker fixed repeated integration-only Ruff import ordering after two unsuccessful tester attempts."
model_fallback: true
last_verified: 2026-07-30
updated: 2026-07-30
card_path: knowledge/tasks/document-optimizer-block-13-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 60df82430d430ff865ebfe6677ec974dd3b734e2
branch: codex/block-13-calculation-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block13-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/calculation
  - tests/fixtures/calculation
  - tests/contract/test_block13_calculation_contract.py
  - tests/integration/test_block13_calculation_engine.py
  - tests/integration/test_block13_real_data.py
source_paths:
  - tests/unit/calculation
  - tests/fixtures/calculation
  - tests/contract/test_block13_calculation_contract.py
  - tests/integration/test_block13_calculation_engine.py
  - tests/integration/test_block13_real_data.py
depends_on: []
forbidden_paths:
  - src
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
  - tests/conftest.py
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  public_api: CalculationEngine-13.0
  contract: CalculationContract-13.0
acceptance_commands:
  - "uv run --extra dev ruff check tests/unit/calculation tests/fixtures/calculation tests/contract/test_block13_calculation_contract.py tests/integration/test_block13_calculation_engine.py tests/integration/test_block13_real_data.py"
  - "uv run --extra dev ruff format --check tests/unit/calculation tests/fixtures/calculation tests/contract/test_block13_calculation_contract.py tests/integration/test_block13_calculation_engine.py tests/integration/test_block13_real_data.py"
  - "uv run --extra dev pytest tests/unit/calculation tests/contract/test_block13_calculation_contract.py tests/integration/test_block13_calculation_engine.py -q"
  - "DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX='<source>' DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX='<target>' uv run --extra dev pytest tests/integration/test_block13_real_data.py -q"
tags:
  - task/implementation
  - status/claimed
  - layer/test
  - risk/high
---

# Block 13 tests

Только test/fixture scope. Покрыть Decimal-only и запрет float/non-finite,
aggregate-then-round, coefficient, explicit zero против missing, signed
negative adjustments, unit policy, allowed units, independent quantity/cost
flags, EXCLUDE/REVIEW, selected-only, ambiguous/unmatched, category totals,
UNCLASSIFIED без text inference, provenance, formula trace, duplicate input
identities, stable IDs/order/digest и отсутствие workbook writes.

Real-data test получает пути только через environment. Запустить блоки 8–13
на существующих книгах, зафиксировать counts/status/digest и проверить
SHA-256, size и mtime обеих книг до/после.
