---
type: task
status: in_progress
card_id: reconciliation-max-accuracy-audit-v1
version: 1
work_id: reconciliation-max-accuracy-audit-v1
task_id: integration
purpose: Prove the current document-reconciliation path against its algorithm and private workbook evidence.
role: worker
agent_role: orchestrator
owner: root
profile: L3
routing_grade: P5
assigned_model: gpt-5.6-sol
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-sol
actual_reasoning_effort: medium
source_base_sha: 8d87a2c96ec3a26b3263cbff157755d18d07ec05
write_scope: []
source_paths:
  - src/report_processor/admin_panel/reconciliation_*
  - src/report_processor/reconciliation_review
  - src/report_processor/reconciliation_grouping
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - tests
tags:
  - task/review
  - status/in-progress
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[../components/reconciliation|Сверка документов]]"
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Аудит максимальной точности сверки

## Objective

Map the exact production algorithm, compare original/target/result workbooks independently,
enumerate edge cases, reproduce every material risk and leave a compact evidence-backed handoff.

## Scope and invariants

- Audit current `main`; do not activate inert shadow/Qdrant paths or change product policy.
- Inspect private workbooks locally, but record only aggregate/de-identified evidence in Git.
- Preserve every source, target, result and unrelated drawing-card specification byte-for-byte.
- Code, tests and direct cell/formula inspection override historical notes.
- Use Code Graph before manual code search and the spreadsheet runtime for direct workbook inspection.

## Current evidence

- Canonical local/remote `main`: `30eeafade56658d46a022eae00f5cf59928a3a55`.
- Code Graph exposed the production chain through `prepare_review`, `_sources`,
  `apply_overrides`, `calculate_matches`, `writer_calculations` and verified publication.
- Baseline: `327 passed, 3 skipped`; real-data checks are environment-gated and require
  independent local evidence.

Representative de-identified run: 12 sources, 2,953 extracted rows, 989 visible rows,
250 groups, 211 packages and a verified result. One unaffected row independently traced the
original cumulative formula caches through Decimal arithmetic to the exact two changed target
cells. Direct audit then found RA-001: one cumulative workbook was silently selected as KS-2,
using contract metrics and producing a demonstrably wrong authoritative output when accepted.
See [[../errors/reconciliation-accuracy-findings|finding catalog]].

## Risks to resolve

- Cached formula values, merged/multi-row headers, duplicate categories and ambiguous indices.
- Decimal/rounding, quantity-versus-cost modes, zero/negative/non-finite values and unit drift.
- Group/package membership, stale decisions, feedback replay and concurrency/restart behavior.
- OOXML preservation, target addressing, unchanged-copy identity and result verification gaps.

## Acceptance

- Every algorithm stage has source/test evidence and an explicit invariant/result.
- At least one representative private corpus is independently reconciled from originals to output.
- Material gaps have a deterministic reproduction and severity; no claim of 100% accuracy without evidence.
- Focused and full gates, knowledge validation, final P6 review and clean scoped Git status pass.

## Next step

Run the full suite and independent P6 synthesis, then hand off a prioritized remediation wave.
Production code remains unchanged in this diagnostic task.
