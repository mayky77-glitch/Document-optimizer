---
type: task
card_id: document-optimizer-block-12-tests
status: claimed
version: 1
supersedes: null
work_id: document-optimizer-block-12
task_id: block-12-tests
purpose: "Доказать каскад, неоднозначность, provenance и детерминизм блока 12"
role: worker
agent_role: tester
owner: block-12-tests
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent contract, ambiguity, deterministic and real-data verification."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
card_path: knowledge/tasks/document-optimizer-block-12-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 2374e8a40aa34291e765e7f072ee4fc733bb5f4c
branch: codex/block-12-matching-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block12-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/matching
  - tests/contract/test_block12_matching_contract.py
  - tests/integration/test_block12_matching_engine.py
  - tests/integration/test_block12_real_data.py
  - tests/fixtures/matching
source_paths:
  - tests/unit/matching
  - tests/contract/test_block12_matching_contract.py
  - tests/integration/test_block12_matching_engine.py
  - tests/integration/test_block12_real_data.py
  - tests/fixtures/matching
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
  public_api: MatchingEngine-12.0
  contract: MatchingContract-12.0
acceptance_commands:
  - "uv run --extra dev ruff check tests/unit/matching tests/contract/test_block12_matching_contract.py tests/integration/test_block12_matching_engine.py tests/integration/test_block12_real_data.py"
  - "uv run --extra dev pytest tests/unit/matching tests/contract/test_block12_matching_contract.py tests/integration/test_block12_matching_engine.py"
  - "DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX='<source>' DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX='<target>' uv run --extra dev pytest tests/integration/test_block12_real_data.py -q"
tags:
  - task/implementation
  - status/claimed
  - layer/test
  - risk/medium
---

# Block 12 tests

Только test/fixture scope. Покрыть public contract, семь стратегий, fixed
`Decimal` confidence, все candidates, duplicate identity errors, deterministic
IDs/order/digest, reversed inputs, unique auto-match, ties, REVIEW, EXCLUDE,
fuzzy manual-only, provenance и отсутствие денежных вычислений.

Real-data test получает пути только через environment, ничего не копирует и не
изменяет. Проверить SHA-256, size и mtime обеих книг, один result на target,
отсутствие selected у `AMBIGUOUS`, повторяемость digest и фактические counts.
