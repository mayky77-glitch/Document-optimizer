---
type: task
card_id: reconciliation-source-region-implementation
status: done
work_id: reconciliation-source-region-implementation-v1
purpose: Record the accepted region-first source-layout implementation and verification evidence.
role: worker
agent_role: developer
owner: reconciliation-source-region
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: Fail-closed source-layout extraction with formula-cache integrity and bounded sparse discovery.
launch_status: inherited
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: Historical accepted work; runtime routing metadata was not retained.
model_fallback: false
last_verified: 2026-08-16
updated: 2026-08-16
write_scope:
  - "src/report_processor/admin_panel/reconciliation_sources.py"
  - "tests/unit/admin_panel/test_reconciliation_sources_layout.py"
  - "tests/integration/test_reconciliation_real_data.py"
source_paths:
  - "src/report_processor/admin_panel/reconciliation_sources.py"
  - "tests/unit/admin_panel/test_reconciliation_sources_layout.py"
  - "tests/integration/test_reconciliation_real_data.py"
depends_on: []
tags:
  - task/implementation
  - status/done
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[../components/reconciliation]]"
---

# Region-first source-layout implementation

## Accepted contract

Accepted integration: `4294c15`. Source layouts are discovered from physical
metric regions and exact merged ancestry before role binding. Role binding uses
the shared schema resolver within the local header band; ambiguous layouts,
ambiguous role bindings and unavailable formula caches fail closed with their
controlled outcomes. Sparse discovery is bounded and ignores styled empty
cells while retaining nonempty data, formulas and merge structure.

## Verification evidence

- Final private shadow aggregate: 9 usable sources, 3 controlled ambiguous
  outcomes and 2,787 extracted rows; no output artifact was produced and all
  13 input artifacts remained unchanged.
- Focused verification: 581 passed and 1 opt-in check skipped.
- Independent final review returned `MERGE YES`.

## Residual risk

The sparse limits intentionally reject excessive relevant structural work.
Future changes to parser semantics, formula handling or workbook runtime need
the same opt-in private shadow verification before release.
