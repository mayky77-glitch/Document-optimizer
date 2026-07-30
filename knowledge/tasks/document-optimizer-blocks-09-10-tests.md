---
type: task
card_id: document-optimizer-blocks-09-10-tests
status: claimed
version: 1
supersedes: null
work_id: document-optimizer-blocks-09-10
task_id: blocks-09-10-tests
purpose: "Доказать frozen contracts, Excel immutability и запрет executable configuration"
role: worker
agent_role: tester
owner: blocks-09-10-tests
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent tests and synthetic fixtures for two frozen package contracts."
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
card_path: knowledge/tasks/document-optimizer-blocks-09-10-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - c04008c51d39996788b0bcb9d6465e280d01938c
branch: codex/blocks-09-10-tests
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/unit/target_report
  - tests/unit/business_rules
  - tests/contract/test_block5_to_block9_contract.py
  - tests/contract/test_block10_public_contract.py
  - tests/integration/test_target_report_immutability.py
  - tests/integration/test_read_target_report_cli.py
  - tests/integration/test_validate_business_rules_cli.py
  - tests/fixtures/target_report
  - tests/fixtures/business_rules
source_paths:
  - tests/unit/target_report
  - tests/unit/business_rules
  - tests/contract/test_block5_to_block9_contract.py
  - tests/contract/test_block10_public_contract.py
  - tests/integration/test_target_report_immutability.py
  - tests/integration/test_read_target_report_cli.py
  - tests/integration/test_validate_business_rules_cli.py
  - tests/fixtures/target_report
  - tests/fixtures/business_rules
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
  block_9: "TargetReportRow-9.0 + TargetReportSchema-9.0"
  block_10: "ValidatedRuleSet-10.0 + RuleConfigurationVersion-1.0"
acceptance_commands:
  - "uv run ruff check tests/unit/target_report tests/unit/business_rules tests/contract/test_block5_to_block9_contract.py tests/contract/test_block10_public_contract.py tests/integration/test_target_report_immutability.py tests/integration/test_read_target_report_cli.py tests/integration/test_validate_business_rules_cli.py"
  - "uv run pytest tests/unit/target_report tests/unit/business_rules tests/contract/test_block5_to_block9_contract.py tests/contract/test_block10_public_contract.py tests/integration/test_target_report_immutability.py tests/integration/test_read_target_report_cli.py tests/integration/test_validate_business_rules_cli.py"
tags:
  - task/implementation
  - status/claimed
  - layer/test
  - risk/high
---

# Blocks 9–10 tests

Блок 9: semantic recovery при generic `UNKNOWN_SHEET_TYPE`, period pairs 0/1/many,
shared formulas/cache states, stale calc flags, leading-zero indexes, merged blocks,
fingerprint mismatch, exact Decimal lexemes, deterministic rows, unchanged SHA/stat.

Блок 10: JSON/YAML parity, M01–M15, canonical round-trip/hash, conflicts,
hard-exclude precedence, units, duplicate/unknown keys, malformed Decimal, YAML tags/aliases,
executable payloads, depth/size limits, deterministic ordering. Только synthetic fixtures.
