---
type: task
card_id: document-optimizer-block-13-docs
status: done
version: 1
supersedes: null
work_id: document-optimizer-block-13
task_id: block-13-docs
purpose: "Обновить README и проектную документацию по фактическому calculation contract"
role: worker
agent_role: documentation-agent
owner: block-13-docs
profile: L0
routing_grade: P1
progress_revision: 2
state_fingerprint: ""
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
last_verified: 2026-07-30
updated: 2026-07-30
card_path: knowledge/tasks/document-optimizer-block-13-docs.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 60df82430d430ff865ebfe6677ec974dd3b734e2
branch: codex/block-13-calculation-docs
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block13-docs"
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
  public_api: CalculationEngine-13.0
  contract: CalculationContract-13.0
acceptance_commands:
  - "git diff --check"
tags:
  - task/documentation
  - status/claimed
  - layer/docs
  - risk/low
---

# Block 13 documentation

Обязательно обновить GitHub `README.md`, `ARCHITECTURE`, `PROJECT_STATUS` и
`IMPLEMENTATION_REVIEW`. Описать selected-only границу, Decimal-формулы,
coefficient/rounding, правила включения, signed adjustments, категории и
`UNCLASSIFIED`, trace/provenance, входы/выходы и отсутствие workbook writes.
Не объявлять READY/main и не заявлять test/real-data/CI до фактического
evidence integration owner.
