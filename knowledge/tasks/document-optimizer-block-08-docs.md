---
type: task
card_id: document-optimizer-block-08-docs
status: frozen
version: 1
supersedes: null
work_id: document-optimizer-block-08
task_id: block-08-docs
purpose: "Описать block 8 API, CLI, contracts и фактические ограничения"
role: documentation-agent
owner: block-08-docs
routing_grade: P1
assigned_model: gpt-5.6-luna
reasoning_effort: low
launch_status: planned
card_path: knowledge/tasks/document-optimizer-block-08-docs.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 4e4279f113cd96128c3335c3ca04e765ea833370
branch: codex/block-08-normalization-docs
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - README.md
  - docs/ARCHITECTURE.md
  - docs/PROJECT_STATUS.md
  - docs/IMPLEMENTATION_REVIEW.md
forbidden_paths:
  - src
  - tests
  - pyproject.toml
  - uv.lock
  - knowledge
contract_versions:
  input: TrainingDataRow-7.0
  output: NormalizedSourceRow-8.0
acceptance_commands:
  - "git diff --check"
tags:
  - task/implementation
  - status/in-progress
  - layer/backend
  - risk/medium
---

# Block 8 documentation

Документировать публичные модели, JSONL schema 8.0, CLI `normalize-rows`,
детерминированный business `line_id`, сохранение provenance и ограничения.
READY выставляет integration owner после полного gate.
