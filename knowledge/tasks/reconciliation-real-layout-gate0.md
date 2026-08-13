---
type: orchestration
status: frozen
work_id: reconciliation-real-layout-v1
objective: Make reconciliation and verification exact on the designated real cumulative sources and period-expanded target template.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: 8cc233ebb7830d504983475838cf134a6cd82c1a
published_base_sha_source: exact planning commit containing this manifest and the first frozen card
wave: 1
max_parallel: 1
max_spawns: 6
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-13T19:10:00+08:00
tags:
  - task/implementation
  - status/in-progress
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[admin-verification-accuracy-remediation|Master task]]"
  - "[[../errors/reconciliation-accuracy-findings|RA-019—RA-021]]"
---

# Reconciliation real-layout Gate 0

Wave 1 is accepted at ORDA integration `3364bb3` and published in `main` at `fe3d5ee`. Wave 2 is
accepted at ORDA integration `1362c53` and published in `main` at `959e3b9`. Period insertion starts
from that published checkpoint under [[reconciliation-period-insertion-gate0|a separate Gate 0]].

The lifecycle baseline is `1754 passed, 25 skipped`. Twelve immutable sources, one clean target and
one desired reference were inspected independently. The clean/reference shape is 180 rows and
15→17 columns: J/K stay unchanged, one reporting-period pair appears in L/M, and the narrative
block shifts right. No private basename, path, sheet, coordinate, formula or raw value enters Git,
the API or ORDA state.

Code Graph was invoked before this work. One direct root call returned `Transport closed`; an
independent Code Graph call then succeeded and confirmed the full UI/service/extraction/target/
numeric/publication call path. The generic schema header recognizer has broad non-reconciliation
callers and remains outside this work; the merged-header graph is reconciliation-local. PropExtract
contributes methodology only: exact-or-ambiguous identity, provenance, order-independent consensus
and workbook delta allowlists. Its narrow comparison normalization and code are not adopted.

## Dependency waves

1. [[reconciliation-real-layout-source-identity|source-identity]] builds merged-header candidates and
   one shared terminal identity contract. It preserves the current financial mapping while exposing
   source measure provenance for the next wave.
2. Target-measure starts only from the accepted Wave 1 integration. It structurally distinguishes
   historical documentary totals from an existing current-period pair and moves the numeric oracle
   off fixed J/K. A clean target without the pair fails technically and produces no red artifact.
3. OOXML period-insertion starts only from accepted Wave 2. Reconcile may prepare exactly one pair
   for an explicit `YYYY-MM`, shifting only an audited allowlist of workbook structures. It then
   rereads the prepared target and lets the existing numeric writer operate on that new schema.
4. Service/API/UI starts only from accepted insertion. It persists the optional period in job,
   manifest, recovery and apply identity and exposes the existing reconcile operation explicitly;
   verify stays the default and never invents a period.
5. A read-only private shadow and P6 release review start only after the four write waves.

These waves intentionally overlap target/execution paths and are sequential. Independent read-only
XLSX, architecture and final-review streams may run in parallel; production write scopes may not.
Formulas or workbook objects crossing the insertion boundary block publication unless their exact
translation is explicitly supported. If no calculations are selected, the original target remains
byte-identical and no empty pair is inserted.

## Shared contracts

- `UniversalReconciliationSource-3.0`: merged-span header graph, coherent work/unit/metric region,
  semantic first detail row, physical candidate deduplication and ambiguity failure. No closed
  phrase allowlist.
- `ReconciliationTerminalIdentity-2.0`: leading-zero-safe exact terminal identity plus unique
  target-stage intersection for bounded source candidates; no last-four-digit/year fallback.
- `ReconciliationTargetMeasure-2.0`: current-period pair is structural and carries cell/formula-cache
  provenance; historical J/K is never relabelled by position.
- `ReconciliationPeriodInsertion-1.0`: explicit period, one idempotent insertion, strict OOXML delta
  allowlist, unchanged inputs and verified reopen/digest.

## Release acceptance

- Every card passes its exact focused pytest, Ruff, format and diff gates; every accepted wave is
  merged `--no-ff` and receives an independent high-risk review.
- Private shadow runs from immutable copies and records only de-identified counts/digests/statuses.
- Final release compares the generated target with the desired reference semantically and at OOXML
  part level, proves originals unchanged, runs the full suite and validates knowledge separately.
- Test count is not reduced for appearance. Only measured fixture reuse or equivalent parametrized
  consolidation is accepted; boundary and adversarial coverage stays intact.
