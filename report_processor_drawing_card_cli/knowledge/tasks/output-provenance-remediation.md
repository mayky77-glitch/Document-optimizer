---
type: task
status: done
work_id: confirmed-fixes-20260730
role: worker
agent_role: worker
owner: "developer-output-remediation"
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
fallback_reason: "Runtime inherited the developer Terra route; no separate override confirmation was emitted."
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
write_scope:
  - "src/report_processor/drawing_card/output"
  - "src/report_processor/drawing_card/aggregation/aggregator.py"
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/workflow.py"
  - "tests/unit/test_writer_precision.py"
  - "tests/unit/test_aggregation.py"
  - "tests/unit/test_output_validator.py"
  - "tests/integration/test_output_publication.py"
  - "tests/integration/test_workflow.py"
source_paths:
  - "src/report_processor/drawing_card/output"
  - "src/report_processor/drawing_card/aggregation/aggregator.py"
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/workflow.py"
  - "tests/unit/test_writer_precision.py"
  - "tests/unit/test_aggregation.py"
  - "tests/unit/test_output_validator.py"
  - "tests/integration/test_output_publication.py"
  - "tests/integration/test_workflow.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Self-closing XML and per-cell audit provenance remediation

## Goal

Define the concrete outcome before moving this card to `claimed`.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/drawing_card/output/planner.py`, output writer/XML
  rewriter/public API, aggregation and workflow provenance models, and focused
  output/aggregation tests.
- Commands and tests run: `uv run ruff check .` (passed); scoped
  `uv run ruff format --check ...` (passed); focused pytest (8 passed); full
  `uv run pytest` (58 passed). Full `ruff format --check .` still reports an
  existing formatting-only diff in `docs/ТЗ_универсальная_CLI_карточка.md`,
  outside this card's scope.
- Result: target self-closing numeric cells are expanded while retaining their
  attributes; dry-run and writer share the pure per-cell operation planner;
  matching strategies are retained separately for quantity and cost from
  decisions through the card rows and audit operations. Temporary-output
  validation remains before atomic replacement.
- Risks or follow-up: audit fields use explicit `no_matching_value` and
  `template_unit_hint` provenance where no source decision exists; multi-source
  metric strategies are preserved as a tuple and a readable joined string.

## Handoff

Leave this card in `review` until orchestration accepts the result.
