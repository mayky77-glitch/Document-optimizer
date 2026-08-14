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

The accepted target reader no longer treats J/K or any other address as current by position. It
requires one adjacent quantity/total-cost pair with coherent current scope or one exact common
calendar identity; competing, cumulative and conflicting period evidence fails closed. A clean
historical-only target therefore needs the explicit, idempotent insertion governed by
[[../DECISIONS#DO-020: период вставляется только для реальной записи (2026-08-13)|DO-020]] and
[[../tasks/reconciliation-period-insertion-gate0|its Gate 0]].

The direct insertion core is published at `991002a`: it rebuilds a digest-bound structural plan,
changes only an independently proven OOXML allowlist, inverse-verifies the whole semantic delta and
publishes no-clobber. Release compatibility remains intentionally narrower than arbitrary Excel:
the accepted `90e7a73` compatibility layer permits only complete shared-formula groups wholly left
and semantically unaffected; all affected, duplicate or ambiguous formula topology stays
fail-closed under a separate verifier-local parser.
