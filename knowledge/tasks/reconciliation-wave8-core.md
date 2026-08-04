---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave8-v1
task_id: active-learning-core
role: worker
agent_role: developer
owner: wave8-core
profile: L2
routing_grade: P4
routing_reason: "Privacy-safe immutable queue and shadow intent contracts with deterministic bounded ranking"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
source_base_sha: 1a152e344cb5578777479891508533a0c9971f27
branch: codex/wave8-active-learning-core
write_scope:
  - src/report_processor/reconciliation_patterns/active_learning.py
  - tests/contract/test_active_learning_contract.py
  - tests/unit/reconciliation_patterns/test_active_learning.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/reconciliation_grouping
  - src/report_processor/reconciliation_patterns/pattern_registry.py
  - src/report_processor/reconciliation_patterns/feedback_graph.py
depends_on:
  - reconciliation-wave7-v1
tags:
  - task/contract
  - status/done
---

# Wave 8 active-learning core

Define frozen, slotted, privacy-safe `ActiveLearningQueue-1.0`,
`ActiveLearningIntent-1.0` and `ActiveLearningShadowAutosave-1.0` contracts.
Items carry opaque/versioned Wave 4-7 references, controlled presentation codes,
bounded integer aggregates and allowed shadow actions only. The selector is
deterministic and server-owned; it maximizes expected action reduction first,
then uses affected rows/cost, hard-negative proximity, uncertainty, novelty,
document frequency and opaque ID as explicit stable tie-breaks. No floats, raw
terms, paths, coordinates, vectors, confidence values or activation effects.

Shadow actions are `accept_pattern`, `case_only`, `split`, `reject`; `split`
requires canonical complete unique member refs. Exact queue/item versions are
mandatory and stale intent fails closed without mutation.
