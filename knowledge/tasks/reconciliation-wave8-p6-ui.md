---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave8-p6-recovery-v1
task_id: ui-behavior-recovery
role: worker
agent_role: designer
branch: codex/wave8-p6-ui
write_scope:
  - src/report_processor/admin_panel/assets/reconciliation-active-learning.js
  - src/report_processor/admin_panel/assets/admin.js
  - tests/integration/test_reconciliation_active_learning_ui_contract.py
  - tests/integration/test_reconciliation_active_learning_ui_behavior.py
depends_on:
  - core-store-recovery
  - web-contract-recovery
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_active_learning_adapter.py
  - src/report_processor/admin_panel/reconciliation_active_learning_api.py
  - src/report_processor/admin_panel/reconciliation_active_learning_store.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
---

# Wave 8 P6 UI behavior recovery

Consume only the frozen controlled web DTO and exact shadow request shape.
Remove all free display-string inputs and localize controlled codes in JS.
Keep opaque identity only in JS memory, not DOM, restore focus by identity after
reorder/removal, and prevent `renderJob` from overwriting a successful restore.

Add an executable dependency-free Node DOM harness invoked by pytest. Cover
absent/unavailable, server order, unknown/free-field rejection, exact non-split
and nested split requests including autosave CAS, stale state, focus after
reorder/removal and unchanged legacy package review behavior.
