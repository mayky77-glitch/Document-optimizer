---
type: component
tags:
  - knowledge/component
  - domain/document-processing
  - layer/backend
  - capability/admin-panel
  - risk/high
last_verified: 2026-08-13
updated: 2026-08-13
source_paths:
  - src/report_processor/admin_panel/reconciliation_*
  - src/report_processor/reconciliation_review
  - src/report_processor/reconciliation_grouping
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - tests
---

# Сверка документов

## Authoritative path

`operation=reconcile` reads each uploaded source independently, reads one selected target stage,
builds deterministic review packages, applies the immutable effective-decision snapshot, calculates
authorized matches and publishes one verified target workbook. It is adjacent to
[[document-verification|Проверке документов]]: `verify` annotates failed source rows and never writes
the target.

## Current enforced invariants

- Formula and cached-value views are read together; an eligible formula without a trustworthy
  cache is a controlled technical issue.
- Multiple viable source layouts, target stages or duplicate target `(terminal index, category)`
  fail closed. A valid first detail row is found semantically, not by `header + 2`.
- Quantity packages require one known exact normalized unit; no `m`/`km` conversion or UNKNOWN
  mass acceptance exists.
- A physical source identity is `(source SHA-256, exact sheet, exact positive row)` and can
  contribute only once.
- Apply uses immutable private input snapshots, one owned output identity/digest/mode and one
  idempotent SQLite marker with feedback in the same transaction.
- Restart/pruning recovery rebuilds review/apply evidence from immutable uploads plus the atomic
  decision snapshot; durable manifests contain no workbook-derived work/unit values.
- No selected calculations publishes a byte-identical target; selected calculation requires a
  verified output digest.

## Active real-layout boundary

Wave 1 now builds reconciliation-local merged-header regions, binds adjacent quantity/total-cost
leaves to the exact nominated parent and resolves bounded filename candidates by one selected-stage
terminal intersection. Broad work-header stems nominate candidates, while structural overlap and
equal coherent candidates fail closed; no narrow phrase ranking was introduced.

The clean target and desired reference prove that J/K are historical documentary totals and remain
unchanged. The reference inserts the current reporting-period quantity/cost pair in L/M and shifts
the narrative block. Therefore positional J/K writing is superseded by structural
[[../DECISIONS#DO-019: числовая пара цели определяется структурой, а не адресом (2026-08-13)|DO-019]].
See [[../tasks/reconciliation-real-layout-gate0|Real-layout Gate 0]] and
[[../errors/reconciliation-accuracy-findings|RA-021]].
