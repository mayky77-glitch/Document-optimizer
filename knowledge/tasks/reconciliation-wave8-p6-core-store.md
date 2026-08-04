---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave8-p6-recovery-v1
task_id: core-store-recovery
role: worker
agent_role: developer
branch: codex/wave8-p6-core-store
write_scope:
  - src/report_processor/reconciliation_patterns/active_learning.py
  - src/report_processor/admin_panel/reconciliation_active_learning_store.py
  - tests/contract/test_active_learning_contract.py
  - tests/unit/reconciliation_patterns/test_active_learning.py
  - tests/integration/test_reconciliation_active_learning_adapter.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_active_learning_adapter.py
  - src/report_processor/admin_panel/reconciliation_active_learning_api.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/reconciliation_patterns/pattern_registry.py
  - src/report_processor/reconciliation_patterns/feedback_graph.py
---

# Wave 8 P6 core/store recovery

Red-first close three defects. Reject `SPLIT` when an item has fewer than two
members. Serialize the complete load-check-transition-replace operation with a
private per-path inter-thread/inter-process lock so two callers using the same
autosave fingerprint yield exactly one success and one stale conflict. Rebind
every decoded current/previous intent to the exact queue item, fingerprint,
allowed action, row-override and complete split membership before returning it.

The lock contains no data, rejects symlinks/non-regular files and uses `0600`.
No runtime wiring or persistence beyond the inert shadow store.
