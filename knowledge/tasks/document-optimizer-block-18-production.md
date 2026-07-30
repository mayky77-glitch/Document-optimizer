---
type: task
card_id: document-optimizer-block-18-production
status: completed
version: 1
work_id: document-optimizer-block-18
task_id: block-18-production
purpose: "Реализовать StageRelationRAG-18.0 и минимальный локальный RuBERT adapter"
agent_role: developer
owner: "block-18-production"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: "rag-4c813a1-full-603-pass"
no_progress_count: 0
circuit_state: closed
routing_reason: "New optional model boundary, deterministic retrieval and safe manual-review semantics."
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: completed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-18-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 322cb9ce08f14c017dbdc3bf16c5b91b33238e63
branch: codex/block-18-rag-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block18-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/stage_rag
forbidden_paths:
  - src/report_processor/processing
  - src/report_processor/matching
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
  - .github
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  rag: StageRelationRAG-18.0
  model: RuBERTTiny2Embedding-18.0
acceptance_commands:
  - "uv run ruff check src/report_processor/stage_rag"
  - "uv run ruff format --check src/report_processor/stage_rag"
  - "uv run python -m compileall -q src/report_processor/stage_rag"
tags:
  - task/implementation
  - status/done
  - layer/backend
  - risk/high
---

# Block 18 production

Implement only the frozen RAG package. Keep Block 12 authoritative; semantic-only
results are deterministic manual-review suggestions. Do not add dependencies or
wiring outside `write_scope`.

Accepted locally in integration: pinned model smoke, clean `[rag]` install and
full real+model+slow suite **603 passed in 119.80s**.
