---
type: task
status: done
work_id: drawing-card-contract-check-rag-v1
role: worker
agent_role: orchestrator
owner: "orchestrator"
profile: L3
routing_grade: P5
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Cross-component planning across extraction, XLSX output, feedback lifecycle, tests, and knowledge"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-sol
reasoning_effort: medium
launch_status: confirmed
actual_model: "gpt-5.6-sol"
actual_reasoning_effort: "medium"
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope: []
source_paths:
  - docs/PRD_CONTRACT_VALUES_AND_RAG_FEEDBACK.md
  - src/report_processor/drawing_card/models.py
  - src/report_processor/drawing_card/sources/schema.py
  - src/report_processor/drawing_card/sources/extractor.py
  - src/report_processor/drawing_card/aggregation/aggregator.py
  - src/report_processor/drawing_card/output
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/drawing_card/review/inline.py
depends_on: []
tags:
  - "task/implementation"
  - "domain/drawing-card"
  - "task/research"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[../components/drawing-card|Карточка остатков]]"
---

# План проверки договорной стоимости и исправления feedback

## Goal

Add four aggregates to existing drawing-card rows, detect contract overruns with
a 1,000-ruble tolerance, publish linked discrepancies only when present, and
make exact manual feedback survive the successful rerun lifecycle.

## Scope and instructions

- PRD: [договорные значения и память RAG](../../docs/PRD_CONTRACT_VALUES_AND_RAG_FEEDBACK.md).
- Volumes reuse current quantity source rows; costs reuse current cost source rows.
- Empty rendered values are zero. Internal arithmetic stays Decimal/rubles;
  published costs use million rubles.
- Highlight only contract-cost cell when performed exceeds contract by more
  than 1,000 rubles.
- Create `Расхождения и ошибки` only when at least one violation exists.
- Exact RAG identity is normalized work name plus normalized unit. Similar text
  and different units still require review.

## Completion evidence

- Changed paths: production implementation, tests, PRD and vault cards.
- Production integration commit: `267437b`; extraction commits: `5f33ee4`, `4778c47`.
- Commands and tests run: CodeGraph indexed 487 files / 6,067 nodes / 16,893
  edges. Read-only real-run diagnosis compared two repeated three-row reviews.
- Result: four aggregates, strict discrepancy output and snapshot-based exact RAG replay are implemented.
- Risks or follow-up: multi-row Excel headers contain duplicate parent labels;
  exact leaf resolution must be covered by real fixtures.

## Handoff

Implementation and focused/full verification complete. Keep only the latest two test-run summaries in [[../components/drawing-card]].
