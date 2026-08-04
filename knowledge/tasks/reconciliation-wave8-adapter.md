---
type: task
status: draft
card_status: frozen
version: 1
work_id: reconciliation-wave8-v1
task_id: active-learning-adapter
role: worker
agent_role: developer
owner: wave8-adapter
profile: L2
routing_grade: P4
routing_reason: "Pure Wave 4-7 projection plus atomic private shadow persistence and stale-safe intents"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
source_base_sha: 1a152e344cb5578777479891508533a0c9971f27
branch: codex/wave8-active-learning-adapter
write_scope:
  - src/report_processor/admin_panel/reconciliation_active_learning_adapter.py
  - src/report_processor/admin_panel/reconciliation_active_learning_api.py
  - src/report_processor/admin_panel/reconciliation_active_learning_store.py
  - tests/unit/admin_panel/test_reconciliation_active_learning.py
  - tests/integration/test_reconciliation_active_learning_adapter.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/reconciliation_batch_store.py
  - src/report_processor/admin_panel/reconciliation_batch_presentation.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/reconciliation_grouping
  - src/report_processor/reconciliation_patterns/pattern_registry.py
  - src/report_processor/reconciliation_patterns/feedback_graph.py
depends_on:
  - active-learning-core
tags:
  - task/implementation
  - status/draft
---

# Wave 8 inert adapter and shadow store

Build a pure optional projection from accepted Wave 4-7 DTOs into the frozen
active-learning queue. Keep shadow intent state entirely separate from legacy
`ReconciliationReviewState`. The API parser/state is unregistered in production
routes. Stale queue/item versions return a controlled conflict with zero
mutation. Existing row overrides block affected items.

Persist only opaque IDs, versions, action and controlled split refs in a
job-private atomic-replace file with mode `0600`. Provide one-step shadow undo;
never call registry transitions, feedback persistence, review apply,
calculation or writer code.
