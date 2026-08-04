---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave8-v1
task_id: active-learning-ui
role: worker
agent_role: designer
owner: wave8-ui
profile: L2
routing_grade: P4
routing_reason: "Optional accessible operator queue with strict absent-state compatibility and responsive interaction states"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
source_base_sha: 1a152e344cb5578777479891508533a0c9971f27
branch: codex/wave8-active-learning-ui
write_scope:
  - src/report_processor/admin_panel/assets/reconciliation-active-learning.js
  - src/report_processor/admin_panel/assets/index.html
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/assets/admin.css
  - tests/integration/test_reconciliation_active_learning_ui_contract.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/assets/reconciliation-batches.js
  - src/report_processor/admin_panel/assets/reconciliation-batch-filters.js
  - src/report_processor/reconciliation_grouping
depends_on:
  - active-learning-core
tags:
  - task/design
  - status/done
---

# Wave 8 optional operator UI

Add an inline active-learning section only when `active_learning_queue` is
present; absence must preserve existing package review behavior. Render the
server order without client re-ranking. Lead with proposed category/mode,
expected action reduction, coverage, differences, exceptions and independent
support counts. Exact composition stays expandable.

Support absent/loading/empty/ready/saving/saved/stale/unavailable states and all
four shadow actions. Use native labelled controls, `textContent`, polite live
status, deterministic focus restoration, one-column 390px layout, visible
focus, reduced motion and current light/dark tokens. Do not expose opaque IDs,
versions, evidence, paths, coordinates, confidence/model signals or private
negative content. Do not add mass activation.
