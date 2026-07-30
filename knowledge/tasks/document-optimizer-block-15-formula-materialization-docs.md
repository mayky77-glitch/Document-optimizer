---
type: task
card_id: document-optimizer-block-15-formula-materialization-docs
status: done
version: 1
supersedes: document-optimizer-block-15-docs
work_id: document-optimizer-block-15-formula-materialization
task_id: block-15-formula-docs
purpose: "Обновить README и проектную документацию для numeric-only XLSX output"
role: worker
agent_role: documentation-agent
owner: block-15-formula-docs
profile: L0
routing_grade: P1
progress_revision: 2
state_fingerprint: "feature:e25d00b50aee3aa14baafd44d566979b7ffa0afc;integration:cfab6bc197d845de49f54e75659b4aa9b85b0532"
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded factual documentation-only update including GitHub README."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-luna
reasoning_effort: low
launch_status: confirmed
actual_model: gpt-5.6-luna
actual_reasoning_effort: low
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-15-formula-materialization-docs.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - c8406336211bbabeee9953f6526ba5fde6f0de50
branch: codex/block-15-formula-materialization-docs
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block15-formula-docs"
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
  - .github
  - knowledge
  - .codex
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  public_api: ExcelWriterEngine-15.1
  contract: ExcelWriterContract-15.1
acceptance_commands:
  - "git diff --check"
tags:
  - task/documentation
  - status/done
  - layer/docs
  - risk/low
---

# Block 15.1 documentation

Обновить GitHub README и три проектных документа. Зафиксировать: финальный XLSX
содержит только числа; формулы не попадают в пользовательский отчёт; temporary
copy пересчитывается LibreOffice; оригинал неизменен; ошибки пересчёта блокируют
publication; контракт 15.1.

Не объявлять READY/main и не заявлять test, real-data или CI до evidence
integration owner.
