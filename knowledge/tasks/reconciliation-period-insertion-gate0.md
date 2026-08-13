---
type: orchestration
status: frozen
work_id: reconciliation-period-insertion-v1
objective: Add one explicit reporting-period pair without changing historical target facts or unsupported OOXML state.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: 959e3b94bca5c441b56a12f3bb22d371c79567de
published_base_sha_source: exact planning commit containing this manifest and both task cards
wave: 1
max_parallel: 1
max_spawns: 5
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-13T22:30:00+08:00
tags:
  - task/implementation
  - status/in-progress
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[reconciliation-real-layout-gate0|Real-layout dependency plan]]"
  - "[[reconciliation-period-ooxml|OOXML transformer]]"
  - "[[reconciliation-period-apply|Preview/apply integration]]"
  - "[[../errors/reconciliation-accuracy-findings|RA-021]]"
---

# Reconciliation period-insertion Gate 0

Published base is accepted target-measure checkpoint `959e3b9`. Code and tests override this card.
Code Graph confirmed that the existing writer mutates exact target cells but has no structural
column-insertion primitive. A low-load immutable target/reference comparison proved a two-column
insertion with exact A1 translation of every mapped formula/range; the one extra formula is a
calculated cost fact, not template structure. No private path, filename, sheet, coordinate, formula
or raw workbook value enters Git or orchestration state.

Two production tasks are strictly sequential. [[reconciliation-period-ooxml|OOXML transformer]]
freezes period/anchor/plan contracts and independently verifies one safe transformed private copy.
Only after its P6 acceptance may [[reconciliation-period-apply|preview/apply integration]] expose
future coordinates to review and prepare the workbook after an actionable calculation exists.
Service, API and UI period input remain a later wave.

One developer write stream runs at a time. No private corpus test and no full suite runs inside the
feature tasks. Integration uses merge commits, focused gates and one independent high-risk review
per task. The final private shadow and full suite run once, under reduced scheduling priority.

## Shared contracts

- `ReconciliationPeriodInsertion-1.0`: strict `YYYY-MM`, structural historical anchor, two adjacent
  unmerged future measure columns and deterministic plan digest.
- `ReconciliationPeriodInsertionDelta-1.0`: expected changed parts derive from the plan; unaffected
  ZIP entries remain byte-identical; inverse coordinate translation proves all pre-existing cells,
  formulas, merges and ranges.
- `ReconciliationTargetInsertionPreview-1.0`: non-writable virtual rows use original target digest
  plus future exact coordinates; prepared strict-read rows must reproduce the same catalog.
- `ReconciliationApplyIntegrity-3.0`: period and insertion-plan digest participate in catalog,
  target and apply identities.

## Release invariants

- `verify` never calls the planner or transformer and never inserts a period.
- Missing pair plus missing/invalid period is a controlled technical result.
- No actionable calculated values publishes the original target byte-for-byte and leaves no
  prepared workbook.
- Existing valid current pair is idempotent: no second pair is inserted. Mixed existing/missing
  participating sheets fail closed.
- No fixed column, target phrase, private template exception or narrow header normalization.
- `openpyxl.save()` and LibreOffice are forbidden for insertion. The established final writer may
  still execute its separately accepted formula-materialization contract after preparation.
- Unsupported coordinate-bearing OOXML blocks before publication; originals remain digest-bound
  and unchanged.
