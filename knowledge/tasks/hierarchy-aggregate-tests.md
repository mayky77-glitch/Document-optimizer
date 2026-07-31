---
type: task
status: done
work_id: hierarchy-aggregate-v1
role: worker
agent_role: tester
owner: "tester-1"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: "34d7e986638ccd8562f175bffb4fa0dca3d65a5f"
no_progress_count: 0
circuit_state: closed
routing_reason: "Focused hierarchy, schema inference, workflow, and regression contracts"
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
write_scope:
  - "tests/unit/hierarchy/**"
  - "tests/unit/schema/test_hierarchy_position_detection.py"
  - "tests/unit/training_data/test_hierarchy_aggregates.py"
  - "tests/unit/drawing_card/test_hierarchy_aggregates.py"
  - "tests/unit/admin_panel/test_hierarchy_presentation.py"
  - "tests/integration/test_hierarchy_workflows.py"
source_paths:
  - "src/report_processor/hierarchy/**"
  - "src/report_processor/schema/**"
  - "src/report_processor/training_data/**"
  - "src/report_processor/drawing_card/**"
depends_on:
  - "20d44e15e8a2c57affd2be6fbfdf0c682c02ab3e"
tags:
  - "task/tests"
  - "status/done"
  - "hierarchy"
  - "reconciliation"
  - "drawing-card"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Verify hierarchical aggregate exclusion

## Frozen acceptance

- Nested parents are excluded and leaves remain in source order.
- `6.1`/`6.10` and `...1`/`...1а` are siblings.
- Duplicate and missing codes do not cause unrelated rows to disappear.
- Direct-child totals are compared with deterministic decimal tolerance.
- Header variants and content-mask fallback are accepted only when unambiguous.
- Weak/tied masks fail closed.
- Both reconciliation and drawing-card remainder workflows use the same hierarchy
  semantics and never restore a parent through review.
- Original real workbooks remain byte-identical.

## Completion evidence

- Changed paths: focused hierarchy, schema, training, drawing-card and admin tests.
- Commands and tests run: focused `20 passed`; full `662 passed, 22 skipped`;
  slow performance `4 passed`.
- Result: feature `34d7e986638ccd8562f175bffb4fa0dca3d65a5f`; accepted merge
  `6edec73f4df690947c6223ba20a033f1abb892c7`.
- Risks or follow-up: real XLSB pass measured 37,695 rows and preserved source SHA.

## Handoff

Accepted by integration owner.
