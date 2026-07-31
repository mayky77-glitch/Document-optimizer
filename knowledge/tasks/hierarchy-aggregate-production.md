---
type: task
status: claimed
work_id: hierarchy-aggregate-v1
role: worker
agent_role: developer
owner: "developer-1"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Shared hierarchy, hybrid position-column detection, and two workflow integrations"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
write_scope:
  - "src/report_processor/hierarchy/**"
  - "src/report_processor/schema/column_aliases.py"
  - "src/report_processor/schema/column_resolver.py"
  - "src/report_processor/schema/analyzer.py"
  - "src/report_processor/adapters/ks2/adapter.py"
  - "src/report_processor/adapters/ks6a/adapter.py"
  - "src/report_processor/adapters/svvr/adapter.py"
  - "src/report_processor/training_data/models.py"
  - "src/report_processor/training_data/processor.py"
  - "src/report_processor/processing/adapters.py"
  - "src/report_processor/admin_panel/presentation.py"
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/statuses.py"
  - "src/report_processor/drawing_card/workflow.py"
  - "src/report_processor/drawing_card/sources/schema.py"
  - "src/report_processor/drawing_card/sources/extractor.py"
  - "src/report_processor/admin_panel/drawing_card_service.py"
  - "src/report_processor/admin_panel/drawing_card_presentation.py"
  - "src/report_processor/admin_panel/assets/drawing-card.js"
source_paths:
  - "src/report_processor/schema/**"
  - "src/report_processor/adapters/**"
  - "src/report_processor/training_data/**"
  - "src/report_processor/processing/adapters.py"
  - "src/report_processor/drawing_card/**"
depends_on:
  - "20d44e15e8a2c57affd2be6fbfdf0c682c02ab3e"
tags:
  - "task/implementation"
  - "status/claimed"
  - "hierarchy"
  - "reconciliation"
  - "drawing-card"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Exclude hierarchical aggregate rows

## Frozen contract

- Prevent duplicated quantity and cost by excluding non-leaf aggregate positions.
- Parse exact dot-separated segments. `6.1` is an ancestor of `6.1.3`, but not `6.10`.
- A suffix variant such as `...1а` is a sibling, not a child of `...1`.
- Support arbitrary nesting and preserve leaf order.
- Reconciliation uses the detected row-number/position column and `current_period_cost`.
- Drawing-card remainder processing uses the detected numbering column and
  `remaining_total_cost`.
- Detect numbering by controlled header aliases, confirmed by a bounded multi-row
  hierarchy mask. A strong unique content mask may recover a variant header.
- Fail closed on weak or tied column candidates.
- Compare each aggregate cost with its direct children's declared costs. A mismatch
  is a data-integrity review warning; approving a category must not re-add the parent.
- Do not modify workbook inputs.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until integration accepts the feature commit.
