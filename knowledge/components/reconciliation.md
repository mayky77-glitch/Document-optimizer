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

The current source reader now fails ambiguous instead of silently selecting a wrong layout, but its
header ancestry is still column-local and its cumulative leaf window is positional. On the
representative originals this produces false ambiguity. Full dotted target identifiers are also
not yet accepted by the terminal-identity helper.

The clean target and desired reference prove that J/K are historical documentary totals and remain
unchanged. The reference inserts the current reporting-period quantity/cost pair in L/M and shifts
the narrative block. Therefore positional J/K writing is superseded by structural
[[../DECISIONS#DO-019: числовая пара цели определяется структурой, а не адресом (2026-08-13)|DO-019]].
See [[../tasks/reconciliation-real-layout-gate0|Real-layout Gate 0]] and
[[../errors/reconciliation-accuracy-findings|RA-019—RA-021]].
