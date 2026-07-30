---
type: task
card_id: document-optimizer-block-18-tests
status: draft
version: 1
work_id: document-optimizer-block-18
task_id: block-18-tests
purpose: "Добавить E2E, golden, RAG, real-data, performance и release tests"
agent_role: tester
owner: "block-18-tests"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Independent final-system verification across contracts and real read-only inputs."
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-18-tests.md
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 322cb9ce08f14c017dbdc3bf16c5b91b33238e63
branch: codex/block-18-release-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block18-tests"
write_scope:
  - tests/unit/stage_rag
  - tests/fixtures/stage_rag
  - tests/contract/test_block18_release_contract.py
  - tests/integration/test_block18_e2e.py
  - tests/integration/test_block18_golden.py
  - tests/integration/test_block18_rag.py
  - tests/integration/test_block18_real_data.py
  - tests/performance/test_block18_release_performance.py
forbidden_paths:
  - src
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
  - .github
  - "**/*.xlsx"
  - "**/*.xlsm"
acceptance_commands:
  - "uv run ruff check tests/unit/stage_rag tests/fixtures/stage_rag tests/contract/test_block18_release_contract.py tests/integration/test_block18_*.py tests/performance/test_block18_release_performance.py"
  - "uv run pytest -q tests/unit/stage_rag tests/contract/test_block18_release_contract.py tests/integration/test_block18_*.py"
tags:
  - task/implementation
  - status/draft
  - layer/test
  - risk/high
---

# Block 18 tests

Test the frozen contracts through public APIs. Real workbooks come only from
environment paths and remain byte-for-byte unchanged. Use a deterministic fake
encoder for normal CI and an opt-in exact-model smoke test.
