---
type: task
card_id: document-optimizer-block-17-tests
status: draft
version: 1
supersedes: null
work_id: document-optimizer-block-17
task_id: block-17-tests
purpose: "Проверить ProcessingContract-17.0, CLI, modes, bulk, resume, safety и real XLSX"
role: worker
agent_role: tester
owner: "block-17-tests"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent contract, CLI, mode, resume and real-data verification."
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
card_path: knowledge/tasks/document-optimizer-block-17-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - ca6300471b52ba1ef80585b3881cb77e04a6be50
branch: codex/block-17-processing-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block17-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "tests/unit/processing"
  - "tests/fixtures/processing"
  - "tests/contract/test_block17_processing_contract.py"
  - "tests/integration/test_block17_workflow.py"
  - "tests/integration/test_block17_cli.py"
  - "tests/integration/test_block17_bulk_resume.py"
  - "tests/integration/test_block17_real_data.py"
source_paths:
  - "tests/unit/processing"
  - "tests/fixtures/processing"
  - "tests/contract/test_block17_processing_contract.py"
  - "tests/integration/test_block17_workflow.py"
  - "tests/integration/test_block17_cli.py"
  - "tests/integration/test_block17_bulk_resume.py"
  - "tests/integration/test_block17_real_data.py"
depends_on: []
forbidden_paths:
  - src
  - README.md
  - docs
  - tests/conftest.py
  - pyproject.toml
  - uv.lock
  - .gitignore
  - .github
  - knowledge
  - .codex
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  request_result: ProcessingContract-17.0
  engine: ProcessingEngine-17.0
  state: ProcessingState-17.0
acceptance_commands:
  - "uv run --extra dev ruff check tests/unit/processing tests/contract/test_block17_processing_contract.py tests/integration/test_block17_*.py"
  - "uv run --extra dev ruff format --check tests/unit/processing tests/contract/test_block17_processing_contract.py tests/integration/test_block17_*.py"
  - "uv run --extra dev pytest -q tests/unit/processing tests/contract/test_block17_processing_contract.py tests/integration/test_block17_workflow.py tests/integration/test_block17_cli.py tests/integration/test_block17_bulk_resume.py"
tags:
  - "task/implementation"
  - "status/draft"
  - "layer/backend"
  - "risk/high"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Block 17 tests

## Goal

Black-box tests for frozen ProcessingContract-17.0. Expected pre-merge import
failures are allowed; after production merge the complete focused set must pass.

## Scope

- Modify only `write_scope`.
- Cover all modes/states/exit groups, strictness, bulk isolation and resume hash checks.
- Real files stay read-only through environment paths and private temporary output.
- Verify inspect/dry-run create no XLSX and write keeps no-clobber behavior.

## Handoff

Commit and push the feature branch. Leave the card for integration-owner updates.
