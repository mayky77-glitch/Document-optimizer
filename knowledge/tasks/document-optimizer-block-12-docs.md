---
type: task
card_id: document-optimizer-block-12-docs
status: claimed
version: 1
supersedes: null
work_id: document-optimizer-block-12
task_id: block-12-docs
purpose: "Описать фактический matching contract и ограничения блока 12"
role: worker
agent_role: documentation-agent
owner: block-12-docs
profile: L0
routing_grade: P1
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded factual documentation-only update."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-luna
reasoning_effort: low
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
card_path: knowledge/tasks/document-optimizer-block-12-docs.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 2374e8a40aa34291e765e7f072ee4fc733bb5f4c
branch: codex/block-12-matching-docs
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block12-docs"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - README.md
  - docs/ARCHITECTURE.md
  - docs/IMPLEMENTATION_REVIEW.md
  - docs/PROJECT_STATUS.md
source_paths:
  - README.md
  - docs/ARCHITECTURE.md
  - docs/IMPLEMENTATION_REVIEW.md
  - docs/PROJECT_STATUS.md
depends_on: []
forbidden_paths:
  - src
  - tests
  - pyproject.toml
  - uv.lock
  - knowledge
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  public_api: MatchingEngine-12.0
  contract: MatchingContract-12.0
acceptance_commands:
  - "git diff --check"
tags:
  - task/documentation
  - status/claimed
  - layer/docs
  - risk/low
---

# Block 12 documentation

Описать семь стратегий, порядок выбора, Decimal confidence, сохранение всех
кандидатов, `MATCHED`/`AMBIGUOUS`/`UNMATCHED`, запрет fuzzy auto-selection,
provenance, входы/выходы и границу ответственности. Не объявлять READY/main и
не заявлять тесты, real-data или CI до фактического evidence.
