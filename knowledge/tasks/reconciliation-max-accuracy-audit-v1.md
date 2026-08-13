---
type: task
status: done
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
source_base_sha: 7aa8d30e5abbd49b6d5b9e76b03122c0f447f51e
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

# Аудит максимальной точности проверки и сверки

## Objective

Map the exact user-facing verification algorithm and adjacent reconciliation path, compare
original/target/result workbooks independently, reproduce every material risk and leave a compact
evidence-backed handoff.

## Scope and invariants

- Audit current `main`; do not activate inert shadow/Qdrant paths or change product policy.
- Inspect private workbooks locally, but record only aggregate/de-identified evidence in Git.
- Preserve every source, target, result and unrelated drawing-card specification byte-for-byte.
- Code, tests and direct cell/formula inspection override historical notes.
- Use Code Graph before manual code search and the spreadsheet runtime for direct workbook inspection.

## Final evidence

- Audited product SHA: `7aa8d30e5abbd49b6d5b9e76b03122c0f447f51e`; production code was not changed.
- Code Graph exposed both shared and adjacent paths before its root transport later closed.
- Full gate: `1667 passed, 25 skipped`; focused reconciliation gate: `327 passed, 3 skipped`;
  final verification/writer/API gate: `35 passed`.

Representative de-identified run: 12 sources, 2,953 extracted rows, 989 visible rows,
250 groups, 211 packages and a verified result. One unaffected row independently traced the
original cumulative formula caches through Decimal arithmetic to the exact two changed target
cells in adjacent `reconcile`.

The user-facing `/` route is `operation=verify`: it never writes target J/K and never compares
source quantity/cost with target numeric values. Direct verification audit found four release
blockers: RA-014 missing numeric oracle, RA-001 wrong real layout with 10 false red rows, RA-015
real-workbook annotation failure across all 12 sources and RA-017 hidden-stage false failures.
See [[../errors/reconciliation-accuracy-findings|finding catalog]] and
[[../components/document-verification|verification component]].

## Unresolved risks

- Cached formula values, merged/multi-row headers, duplicate categories and ambiguous indices.
- Decimal/rounding, quantity-versus-cost modes, zero/negative/non-finite values and unit drift.
- Group/package membership, stale decisions, feedback replay and concurrency/restart behavior.
- OOXML preservation, target addressing, unchanged-copy identity and result verification gaps.

## Acceptance result

- Every material stage has source/test/runtime evidence and a scoped `verify`/`reconcile` result.
- Representative private inputs were inspected independently; their digests remained unchanged.
- Material gaps have deterministic reproductions and severity; 100% accuracy is explicitly rejected.
- Independent P6 review rejected release accuracy claims and supplied a must-fix order.
- External [[../research/propextract-methods-2026-08-13|PropExtract]] comparison contributed
  commit-pinned methodology only; no external code or fixtures entered the repository.
- Focused and full product gates pass. Global knowledge validation remains blocked by historical
  schema debt unrelated to this audit; the audit's own link/card defects were corrected.

## Handoff

Production code remains unchanged. Start
[[admin-verification-accuracy-remediation|the remediation card]] only after the owner defines the
meaning of numeric correctness and the target-stage selection contract.
