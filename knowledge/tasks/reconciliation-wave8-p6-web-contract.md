---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave8-p6-recovery-v1
task_id: web-contract-recovery
role: worker
agent_role: developer
branch: codex/wave8-p6-web-contract
write_scope:
  - src/report_processor/admin_panel/reconciliation_active_learning_adapter.py
  - src/report_processor/admin_panel/reconciliation_active_learning_api.py
  - tests/unit/admin_panel/test_reconciliation_active_learning.py
  - tests/contract/test_active_learning_web_contract.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_active_learning_store.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
---

# Wave 8 P6 controlled web contract recovery

Define frozen `ActiveLearningWebQueue-1.0` and
`ActiveLearningShadowRequest-1.0` at the unregistered adapter/API boundary.
The web queue contains only exact queue/item/autosave fingerprints, controlled
kind/mode/presentation/action codes, bounded integer aggregates and canonical
opaque split groups. It contains no title, category label, reason, example,
term, evidence, path, coordinate, confidence, vector or model field.

The producer must preserve server order, bind every item to the source queue,
and only offer split when an exact complete canonical proposal exists. The
request parser consumes one closed shape containing queue, item and autosave
CAS tokens. Keep all production routes unregistered.
