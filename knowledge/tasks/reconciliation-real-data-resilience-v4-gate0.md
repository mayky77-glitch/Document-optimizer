---
type: orchestration
status: frozen
work_id: reconciliation-real-data-resilience-v4
objective: Make authoritative reconciliation process heterogeneous supported workbooks fail-soft, produce grouped actionable review cards, and write verified results.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: 9abfbc9e3773c1474b4caef21faf3164507d8fb9
published_base_sha_source: root planning commit containing this manifest and frozen Wave 1 card
wave: 1
max_parallel: 1
max_spawns: 4
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-02T13:00:00+08:00
tags:
  - knowledge/orchestration
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-source-core-v4]]"
  - "[[reconciliation-real-data-lifecycle-ui-v4]]"
  - "[[reconciliation-real-data-tests-v4]]"
---

# Gate 0: reconciliation real-data resilience

## Product contract

- Each supported source workbook contributes one authoritative row set: use a usable
  КС-6а cumulative "performed for the whole construction period" quantity/cost;
  use КС-2 only as fallback when no usable КС-6а exists. Never add
  alternative source sheets from the same workbook together.
- One bad source is isolated. Good sources still produce review cards. If every
  source is bad, return a controlled failed job, never an empty "ready" review.
- A public source problem contains only the original safe basename, a short Russian
  cause, a short repair hint and whether processing can continue. Paths, sheets,
  coordinates, formulas, exception text, provenance and evidence are forbidden.
- Global review groups deterministically combine all compatible rows by normalized
  semantic name and normalized unit. Broad fuzzy merging is forbidden. Group action
  fans out to all members; an explicit row override remains authoritative.
- Reuse the existing controlled target-category contract and the direct two-state
  `quantity_cost` / `cost_only` switch. Decisions must affect matching,
  `Decimal` calculation, coefficient `2.7`, final XLSX and durable feedback.
- Public numbers use two decimals. The unresolved UI count is the number of cards;
  apply still verifies effective coverage of every member row.

## Root causes frozen at Gate 0

1. The admin adapter omits required `document_index` and `document_period`.
2. Original basenames are discarded when private copies are named `source-XX.xlsx`.
3. The legacy extractor returns zero rows for the 12 real supported workbooks.
4. The generic supported-sheet loop can double-count alternative sheets in one file.
5. The adapter uses period fields instead of the cumulative reconciliation fields
   required by the attached specification.
6. Group sorting compares `None` and `str` units and crashes.
7. One source exception currently fails the entire job and removes the workspace.
8. Empty extraction currently reaches a contradictory empty/ready UI.

## Dependency waves

1. Wave 1: `reconciliation-real-data-source-core-v4` from the exact planning
   commit. It owns source detection/extraction, source issues and grouping only.
2. Wave 2: after Wave 1 is merged and accepted, freeze the exact integration SHA
   for `reconciliation-real-data-lifecycle-ui-v4`. It owns upload metadata,
   lifecycle/presentation and frontend assets. `app.py` remains forbidden and
   `service.py` must have neutral or negative net line growth.
3. Wave 3: after Wave 2 acceptance, freeze and launch
   `reconciliation-real-data-tests-v4` with tests/fixtures only.
4. A final read-only reviewer checks calculation correctness, privacy and fail-soft
   behavior. No auditor is authorized.

Wave 1 was accepted at merge `3145c8cb74e673bb67f097e773f869573c90afc1`.
The target-layout diagnosis is routed through successor Gate 0
`reconciliation-real-data-lifecycle-ui-v4` so its expanded scope is frozen before
implementation.

## Baseline

On parent `9abfbc9e3773c1474b4caef21faf3164507d8fb9`:

- Focused reconciliation/admin set: `33 passed in 0.31s`.
- Real private copies reproduce the missing-arguments `TypeError`.
- Passing `None` only removes the exception: the legacy extractor still yields
  zero rows, while the robust structural detector sees 24,874 candidate rows.
- The target workbook reads 173 target rows for stage `13.1`.

## Release acceptance

- Focused unit/integration tests cover cumulative КС-6а, КС-2 fallback,
  no duplicate contribution, one-bad-source continuation and all-bad controlled
  failure.
- Real-data smoke uses all 12 immutable private input copies and the target,
  produces non-empty rows and fewer complete groups than rows, applies a group and
  row override, then verifies the written OOXML result.
- Browser smoke covers real cards and a safe file-problem card at desktop/mobile in
  light/dark, no console errors and no horizontal overflow.
- Ruff/format, Node syntax and `git diff --check` pass. Full suite is not run.
- Knowledge is updated, the local service is restarted, and the final branch is
  committed and pushed.
