---
type: task
card_id: drawing-card-cable-review-v1-ui
status: draft
version: 1
work_id: drawing-card-cable-review-v1
task_id: ui
purpose: "Показать вложенные строки и стоимость, дать прямой category+cost-only action"
role: worker
agent_role: designer
owner: "designer"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Responsive nested ledger and explicit financial actions need visual QA"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/drawing-card-cable-review-v1-ui.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-cable-review-ui
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "src/report_processor/admin_panel/assets/drawing-card-review.js"
  - "src/report_processor/admin_panel/assets/drawing-card.css"
source_paths:
  - "src/report_processor/admin_panel/assets/drawing-card-review.js"
  - "src/report_processor/admin_panel/assets/drawing-card.css"
depends_on: []
forbidden_paths:
  - "src/report_processor/drawing_card"
  - "src/report_processor/admin_panel/*.py"
  - "tests"
  - "docs"
  - "README.md"
  - "pyproject.toml"
  - "uv.lock"
contract_versions:
  input: "DrawingCardCableReview-1.0"
  output: "DrawingCardCableReviewUI-1.0"
acceptance_commands:
  - "node --check src/report_processor/admin_panel/assets/drawing-card-review.js"
tags:
  - "task/implementation"
  - "status/draft"
  - "drawing-card"
  - "ui"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Drawing card cable review UI

## Goal

Render a compact expandable ledger for every cluster member, restore aggregate
cost visibility, and let the selected category be applied either fully or
cost-only with two direct buttons.

## Scope and instructions

- Modify only `write_scope`.
- Keep the existing Gazprom-blue visual system and keyboard focus behavior.
- Signature element: a restrained nested ledger table with a visually strong cost column.
- Show aggregate cost in the card context and every member name, unit, quantity and cost.
- Use one category selector and two direct actions: include quantity+cost or cost-only.
- No modal, extra panel or intermediate category-only state.
- Verify desktop and mobile layouts; use semantic table markup or equivalent accessible labels.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Responsive/accessibility evidence:

## Handoff

Commit and push the feature branch. Do not merge or force-push.
