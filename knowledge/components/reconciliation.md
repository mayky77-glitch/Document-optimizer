---
type: component
tags:
  - knowledge/component
  - domain/document-processing
  - layer/backend
  - capability/admin-panel
  - risk/high
last_verified: 2026-08-16
updated: 2026-08-16
source_paths:
  - src/report_processor/admin_panel/reconciliation_*
  - src/report_processor/admin_panel/service.py
  - src/report_processor/reconciliation_review
  - src/report_processor/reconciliation_grouping
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - src/report_processor/work_semantics
  - tests
---

# Сверка документов

## Authoritative path

`operation=reconcile` independently reads every uploaded source, projects one selected target
stage, builds deterministic review packages, applies one immutable effective-decision snapshot,
calculates authorized matches, and publishes one verified target workbook. It is separate from
[[document-verification|Проверки документов]]: `verify` never inserts a period into or writes the
target.

## Source interpretation

- Candidate layouts begin with physical adjacent quantity/total-cost regions, not global header
  Cartesian products.
- Exact merged ancestry and physical intervals bind cumulative versus direct semantics. A later
  table cannot be absorbed by an earlier candidate.
- Work and unit roles are resolved by the shared schema resolver from region-local composed
  headers outside the metric span; ties and heterogeneous mappings fail closed.
- Formula and cached-value views are paired. A structurally eligible formula without a cache is a
  controlled issue, never a silently dropped row.
- One bounded sparse index covers nonempty values, actual formulas, and validated merges. Styled
  empty cells are non-semantic. Cell, merge, candidate, probe, and visit budgets fail closed before
  excess work.
- Multiple viable layouts remain `SOURCE_LAYOUT_AMBIGUOUS`; cumulative precedence never turns a
  second viable cumulative region into an implicit choice.

## Target and period interpretation

- Target base roles are header-authoritative. Only jointly missing document-index and stage roles
  may be recovered from one exact shared anchor-row set with valid detail blocks.
- Quantity/cost pairs are structural, period-aware, adjacent, and unique. Addresses are never
  authoritative by themselves.
- Monetary denomination and `за/на` scopes use versioned work semantics. A full canonical unit is a
  rate; an independently proven reporting scope is a total; unknown or mixed evidence fails closed.
- Historical targets use a read-only virtual preview. Physical insertion occurs only during an
  actionable reconcile apply with an exact `YYYY-MM` period.
- Threaded comments are accepted only under their exact relationship, person, timestamp, reference,
  and XML topology; allowed parts remain byte-preserved.

## Integrity and recovery

- `ReconciliationTargetIdentity-2.0` binds target bytes, stage, optional period/plan, target-measure
  semantics, term canonicalization, UnitOntology, and ReportingScope versions.
- `AdminReconciliationJobManifest-4.0` rejects older semantic manifests. Apply keys, state,
  packages, calculations, replay tokens, and recovery evidence transitively bind the target
  identity.
- Apply uses immutable private input snapshots, one owned output identity/digest/mode, and one
  idempotent SQLite marker with feedback in the same transaction.
- Durable manifests contain no workbook-derived work or unit values. Recovery rebuilds exact
  evidence; review-required jobs expose no result.
- No selected calculations publishes a byte-identical target. A selected calculation requires a
  verified output digest.

## OOXML boundary

The period transformer changes only an independently proven allowlist, inverse-verifies its full
semantic delta, validates local and central ZIP flags, and publishes no-clobber. Shared formulas are
preserved only when complete and wholly unaffected. The ZIP writer deliberately mirrors a bounded
CPython private `_open_to_write` path to preserve source metadata; revalidate this compatibility
after Python standard-library upgrades.

## Release evidence

At product checkpoint `4294c15`, the low-load private shadow reached manual review with nine usable
sources and three controlled ambiguities, 2,787 source rows, no output/apply, and all inputs
unchanged. The focused profile passed `581` tests with one opt-in skip; the full repository passed
`2225` with `25` opt-in skips. Independent source and service reviews found no P0/P1 issue.
