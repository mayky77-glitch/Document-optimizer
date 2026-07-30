---
type: task
status: done
work_id: confirmed-fixes-20260730
role: worker
agent_role: worker
owner: "developer-workflow"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L2 compatibility profile maps to P4."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: "gpt-5.6-terra"
actual_reasoning_effort: high
fallback_reason: "Inherited developer runtime; requested P4 route was retained."
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
write_scope:
  - "src/report_processor/drawing_card/workflow.py"
  - "src/report_processor/drawing_card/statuses.py"
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/matching"
  - "src/report_processor/drawing_card/review"
  - "src/report_processor/drawing_card/sources"
  - "src/report_processor/drawing_card/audit"
  - "src/report_processor/cli.py"
  - "src/report_processor/terminal_ui.py"
  - "tests/unit/test_matching.py"
  - "tests/unit/test_manual_review.py"
  - "tests/unit/test_source_regressions.py"
  - "tests/unit/test_manifest.py"
  - "tests/integration/test_workflow.py"
  - "tests/integration/test_review_flow.py"
source_paths:
  - "src/report_processor/drawing_card/workflow.py"
  - "src/report_processor/drawing_card/statuses.py"
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/matching"
  - "src/report_processor/drawing_card/review"
  - "src/report_processor/drawing_card/sources"
  - "src/report_processor/drawing_card/audit"
  - "src/report_processor/cli.py"
  - "src/report_processor/terminal_ui.py"
  - "tests/unit/test_matching.py"
  - "tests/unit/test_manual_review.py"
  - "tests/unit/test_source_regressions.py"
  - "tests/unit/test_manifest.py"
  - "tests/integration/test_workflow.py"
  - "tests/integration/test_review_flow.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Workflow strictness review sources and audit integrity

## Goal

Make workflow publication deterministic and auditable around source selection,
manual review, strict blockers, and expected validation failures.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `workflow.py`, `statuses.py`, `matching/matcher.py`,
  `review/io.py`, `cli.py`, `terminal_ui.py`, and focused tests.
- Commands and tests run: `.venv/bin/ruff check --select F,I,UP,B,SIM ...`;
  `.venv/bin/pytest`.
- Result: lint selection passed; 38 tests passed. Strict mode now prevents
  publication on manual review, ambiguity, duplicates, unit mismatch, source /
  extraction / formula warnings and update conflicts. Expected request and review
  validation failures leave `error.json` plus `processing_summary.json`.
- Risks or follow-up: Full ruff remains blocked by pre-existing E501 violations
  in scoped modules; no unrelated formatting rewrite was made. Archive inspection
  now evaluates every candidate to avoid silently missing the best actual source;
  very large archives may take longer.

## Proposed knowledge delta

No component card exists yet. After acceptance, add a drawing-card workflow card
documenting strict publication blockers and full-candidate source inspection.

## Handoff

Leave this card in `review` until orchestration accepts the result.
