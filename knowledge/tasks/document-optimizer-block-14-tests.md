---
type: task
card_id: document-optimizer-block-14-tests
status: claimed
version: 1
supersedes: null
work_id: document-optimizer-block-14
task_id: block-14-tests
purpose: "Доказать решения write gate, детерминизм и real-data безопасность блока 14"
role: worker
agent_role: tester
owner: block-14-tests
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent contract, decision-matrix, deterministic and real-XLSX verification."
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
card_path: knowledge/tasks/document-optimizer-block-14-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - d8a55a82997d8f97a14f9287a32900f942ea2229
branch: codex/block-14-quality-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block14-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/quality_control
  - tests/fixtures/quality_control
  - tests/contract/test_block14_quality_control_contract.py
  - tests/integration/test_block14_quality_control.py
  - tests/integration/test_block14_real_data.py
source_paths:
  - tests/unit/quality_control
  - tests/fixtures/quality_control
  - tests/contract/test_block14_quality_control_contract.py
  - tests/integration/test_block14_quality_control.py
  - tests/integration/test_block14_real_data.py
depends_on: []
forbidden_paths:
  - src
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - .github
  - knowledge
  - tests/conftest.py
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  public_api: QualityControlEngine-14.0
  contract: QualityControlContract-14.0
acceptance_commands:
  - "uv run --extra dev ruff check tests/unit/quality_control tests/fixtures/quality_control tests/contract/test_block14_quality_control_contract.py tests/integration/test_block14_quality_control.py tests/integration/test_block14_real_data.py"
  - "uv run --extra dev ruff format --check tests/unit/quality_control tests/fixtures/quality_control tests/contract/test_block14_quality_control_contract.py tests/integration/test_block14_quality_control.py tests/integration/test_block14_real_data.py"
  - "uv run --extra dev pytest -q tests/unit/quality_control tests/contract/test_block14_quality_control_contract.py tests/integration/test_block14_quality_control.py"
  - "DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX='<source>' DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX='<target>' RUN_SLOW=1 uv run --extra dev pytest -q tests/integration/test_block14_real_data.py"
tags:
  - task/implementation
  - status/claimed
  - layer/test
  - risk/high
---

# Block 14 tests

Только test/fixture scope. Покрыть все четыре решения и precedence; empty,
duplicates, cardinality, identities, writable flag, formula/cache/Excel errors,
provenance, category/trace/formula totals, normalized-unit conflicts, independent
quantity/cost inclusion, sign consistency, negative warnings и точную Decimal
tolerance на границе и при нулевом denominator.

Проверить стабильность ID/digest для reverse order, сохранение multiplicity и
отсутствие raw/formula-sensitive payload в отчёте.

Real-data test получает пути только через environment. Запустить блоки 8–14:
ожидается 107 результатов, 101 unmatched, 5 ambiguous, 1 calculated,
`REQUIRE_MANUAL_REVIEW`, без blocking issues. Зафиксировать digest и проверить
SHA-256, size и mtime обеих книг до/после.
