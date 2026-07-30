---
type: task
card_id: document-optimizer-block-11-tests
status: done
version: 1
supersedes: null
work_id: document-optimizer-block-11
task_id: block-11-tests
purpose: "Доказать безопасность SQL, атомарность, дедупликацию и воспроизводимость блока 11"
role: worker
agent_role: tester
owner: block-11-tests
profile: L1
routing_grade: P3
progress_revision: 7
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent contract, integration and adversarial DuckDB verification."
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
card_path: knowledge/tasks/document-optimizer-block-11-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 654c3a4c53971f2e9ae617a36f4089315ef26d36
branch: codex/block-11-analytics-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block11-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/analytics
  - tests/contract/test_block11_analytical_contract.py
  - tests/integration/test_block11_analytical_store.py
  - tests/fixtures/analytics
source_paths:
  - tests/unit/analytics
  - tests/contract/test_block11_analytical_contract.py
  - tests/integration/test_block11_analytical_store.py
  - tests/fixtures/analytics
depends_on: []
forbidden_paths:
  - src
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
  - "**/real-data/**"
contract_versions:
  public_api: AnalyticalStore-11.0
  database_schema: AnalyticalSchema-1
acceptance_commands:
  - "uv run ruff check tests/unit/analytics tests/contract/test_block11_analytical_contract.py tests/integration/test_block11_analytical_store.py"
  - "uv run pytest tests/unit/analytics tests/contract/test_block11_analytical_contract.py tests/integration/test_block11_analytical_store.py"
  - "uv run pytest tests/unit/storage tests/contract/test_duckdb_storage_contract.py"
tags:
  - task/implementation
  - status/claimed
  - layer/test
  - risk/high
---

# Block 11 tests

Только synthetic fixtures. Покрыть public contract, schema validation, exact
Decimal, full provenance/classification/warnings, identical/conflicting IDs,
`line_id` collisions, transaction rollback, deterministic order/export SHA,
parameterized SQL injection values, bounded allowlisted views и regressions
существующего `DuckDBStore` v1. Реальные Excel-файлы не копировать и не менять.
