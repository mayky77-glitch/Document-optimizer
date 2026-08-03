---
type: task
status: review
work_id: drawing-card-contract-check-rag-v1
role: worker
agent_role: worker
owner: "contract-values-developer"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded extraction and immutable model extension before aggregation/output"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/sources/schema.py"
  - "src/report_processor/drawing_card/sources/extractor.py"
source_paths:
  - "src/report_processor/drawing_card/models.py"
  - "src/report_processor/drawing_card/sources/schema.py"
  - "src/report_processor/drawing_card/sources/extractor.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/review"
  - "domain/drawing-card"
  - "capability/xlsx-output"
  - "status/in-progress"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Извлечь договорные и выполненные объёмы и стоимости

## Goal

Extract four immutable contract/performed Decimal values alongside existing remaining metrics.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `src/report_processor/drawing_card/models.py`
  - `src/report_processor/drawing_card/sources/schema.py`
  - `src/report_processor/drawing_card/sources/extractor.py`
- Commands and tests run:
  - `.venv/bin/python -m compileall -q src/report_processor/drawing_card/models.py src/report_processor/drawing_card/sources/schema.py src/report_processor/drawing_card/sources/extractor.py`
  - `.venv/bin/ruff check src/report_processor/drawing_card/models.py src/report_processor/drawing_card/sources/schema.py src/report_processor/drawing_card/sources/extractor.py`
  - `.venv/bin/ruff format --check src/report_processor/drawing_card/models.py src/report_processor/drawing_card/sources/schema.py src/report_processor/drawing_card/sources/extractor.py`
  - `.venv/bin/pytest -q tests/unit/drawing_card/test_hierarchy_aggregates.py` — `3 passed`
  - focused in-memory multi-row-header check: resolved all four columns; empty contract cached cells yielded `Decimal(0)`.
- Result:
  - `DrawingSourceRow` now exposes `contract_quantity`, `contract_total_cost`, `performed_quantity`, and `performed_total_cost`, each defaulting to `Decimal(0)` for backward-compatible construction.
  - Schema resolution selects explicit quantity/cost leaf columns beneath `Стоимость по договору` and `Выполнено за весь период строительства`; tied duplicate leaves resolve to the leftmost column and emit `AMBIGUOUS_COLUMN`.
  - Extraction preserves cached/formula provenance in this fixed tuple order: remaining quantity/cost, contract quantity/cost, performed quantity/cost.
- Risks or follow-up:
  - The current source scope has no real-workbook fixture. Header aliases cover the PRD labels; a real duplicate-header fixture should lock the expected physical columns in the downstream test scope.
  - A formula without a cached value remains warning-bearing and produces `Decimal(0)` for the new rendered metrics.

## Routing

- `route: P3 -> developer / gpt-5.6-terra / medium`; normal scoped production implementation with a multi-row Excel header contract.
- Local pipeline triage: `codex`; private production-code and task-card work is not eligible for assistive provider routing.

## Handoff

Leave this card in `review` until orchestration accepts the result.
