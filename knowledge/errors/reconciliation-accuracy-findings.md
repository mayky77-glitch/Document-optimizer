---
type: error-catalog
status: open
tags:
  - knowledge/error
  - domain/document-processing
  - capability/admin-panel
  - risk/high
last_verified: 2026-08-13
updated: 2026-08-13
source_paths:
  - src/report_processor/admin_panel/reconciliation_*
  - src/report_processor/reconciliation_grouping
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/excel_writer
---

# Reconciliation and verification accuracy findings

Authoritative de-identified handoff for
[[../tasks/reconciliation-max-accuracy-audit-v1|the maximum-accuracy audit]]. Code, tests and
direct workbook evidence override this note. The public `/` workflow is `operation=verify`;
`operation=reconcile` is an adjacent calculation/write path. They share extraction, target
interpretation, matching and grouping, but their outputs are different.

## User-facing verification findings

| ID | Severity | Boundary | Deterministic result |
| --- | --- | --- | --- |
| RA-014 | critical decision gate | verification meaning | `passed` proves classification/feedback only; source and target numbers are never compared |
| RA-001 | high | source classification | one real cumulative source becomes KS-2; 13 rows are checked instead of 3 visible cumulative rows and 10 rows are falsely red |
| RA-015 | high | red-row writer | all 12 representative real workbooks fail annotation with `STYLES_MISSING` |
| RA-017 | high | target stage | UI silently uses `13.1`; an absent stage yields an empty catalog and makes every visible row fail |
| RA-002 | high | source row boundary | a valid first data row can be skipped by fixed `leaf + 2` |
| RA-003 | high | target index | a trailing four-digit year can replace the document index and change matching |
| RA-004 | high | unit/package safety | mixed exact units or distinct unknown units can be mass-safe |
| RA-011 | high | formula cache | formula metrics without cached values disappear from checked/failed coverage |
| RA-018 | high | multi-source publication | failure cleanup can delete a pre-existing ZIP or deterministic temporary workbook |
| RA-012 | medium | service restart | ready results and in-memory job metadata are stranded after restart/pruning |
| RA-016 | medium | duplicate uploads | equal bytes under different names are counted and annotated twice |

## Adjacent reconciliation-only or latent findings

| ID | Severity | Boundary | Scope |
| --- | --- | --- | --- |
| RA-005 | medium latent | mixed-scope autosave restore | not reached by a normal fresh verify job |
| RA-006 | high | feedback/output transaction | `reconcile` apply only; failed apply can persist feedback without a result |
| RA-007 | high | target `.xlsm` | selected target writes fail; no-change output has a misleading `.xlsx` extension |
| RA-008 | high | numeric writer cleanup | concurrent replacement can be deleted after a post-publish failure |
| RA-009 | high | exact-once calculation | accepted source identity can contribute more than once to target arithmetic |
| RA-010 | medium | duplicate target category | last-write-wins can bind the wrong target row; verify impact is indirect |
| RA-013 | low latent | negative-pair API | dangling endpoints are ignored; no current production caller found |

RA-016 is high for `reconcile`: duplicate physical inputs acquire distinct technical row IDs and
can double financial contribution. It is medium for `verify`: checked/failed counts and output
members are duplicated, but the original bytes are not changed.

## RA-014 — verification is not a numeric reconciliation

`verify_reconciliation` declares a row correct when the newest authoritative decision accepts it
or its group belongs to a `DecisionPackage.safe`. Quantity and cost affect zero-row partitioning
and mode selection, but are never compared with target J/K or any target numeric field. A
deterministic real function repro passed a safe row containing deliberately extreme, contradictory
quantity/cost values. The exact success message nevertheless says that all documents were checked
and no errors found.

This matches the historical implementation contract in
[[../tasks/admin-verification-service|admin verification v1]], so it is not an accidental
branch deviation. It is a product-semantic gap. Before implementation, the owner must define
whether “Проверка документов” means classification/membership only or numeric document equality.
If numeric correctness is intended, define authoritative source/target measures, units,
coefficients, aggregation level, Decimal rounding and tolerances; `passed` must be unavailable
until that oracle succeeds.

## RA-001 — wrong real source layout changes verification

`_extract_ks6a_rows` recognizes only a work header containing `наименование этапа`. A real
structurally cumulative workbook uses another valid work/cost wording and contains an explicit
`выполнено за весь период` anchor, but the extractor falls through to generic KS-2. It binds an
earlier contract pair and accepts the displayed column-number row as data.

With identical source bytes, target, stage, feedback and downstream production logic:

- current runtime selected KS-2: 13 canonical, checked and failed rows;
- independently bound cumulative layout selected KS-6a: 12 canonical rows, of which 3 non-zero
  rows were checked and failed;
- the red-row sets overlap on 3 rows; current runtime adds 10 false red rows;
- source and target digests stayed unchanged; the audit-only successful result changed only
  `xl/styles.xml` and one worksheet part, while formulas and values stayed identical.

Production cannot currently return that real red workbook because RA-015 fails first. In adjacent
`reconcile`, an isolated authoritative apply proved the same fallback can write contract values
instead of cumulative values to target J/K. Thus RA-001 is critical for reconcile and high for
verify.

Safe remediation: evaluate structural candidates, accept normalized work-header aliases, bind
quantity/total-cost leaves to the cumulative anchor, find the first detail row semantically, and
fail controlled ambiguity rather than silently fall back. Regression must assert cumulative
precedence, the exact canonical set and no number-row ingestion.

## RA-015/018 — verification publication is not real-workbook safe

`row_annotations._xml_children` uses one greedy regex for self-closing and paired `xf` children.
A self-closing `<xf/>` can be consumed together with the following `<xf>...</xf>`, so the raw
child count differs from namespace-aware `ElementTree`. Every one of the 12 representative source
workbooks has this shape and deterministically raises `STYLES_MISSING: cellXfs structure`; the
service exposes only generic `PROCESSING_FAILED` and deletes the job directory. Existing tests use
simple generated styles and omit mixed `<xf/><xf>...</xf>` adjacency.

Fix the raw child scanner without reserializing unrelated OOXML, add a direct two-style regression
and a de-identified real-structure integration fixture. Reopen/parse the patched package before
publish and project a controlled repair issue rather than a generic failure.

For multiple sources, `_write_artifact` opens the final ZIP with mode `x` and then unconditionally
unlinks that path on any exception. A pre-existing output can therefore be deleted after
`FileExistsError`. Deterministic `verification-source-NN` cleanup has the same ownership flaw.
Use unique private temporary paths plus no-clobber publication, and delete only identities created
by the current attempt.

## RA-017 — hidden stage can create false failures

The verification form has no stage control and posts only files plus `operation=verify`; the server
defaults a missing field to `13.1`. On the representative target, `13.1` selected 87 target rows,
while a missing-stage probe selected zero. An empty selection is not a target error: review state
is created with zero categories/proposals/safe groups, so all 13 visible source rows fail as if the
documents were wrong.

The owner must choose a stage contract: explicit user selection, safe discovery of one unambiguous
stage, or a clearly documented strict default. Zero or ambiguous target scope must be a controlled
input error before row verdicts are produced.

## RA-002/003/004/011/016 — shared correctness guards

- Replace fixed `leaf + 2` with the same semantic detail predicate required by RA-001; blindly
  using `+1` would ingest number rows in other workbooks.
- Use the canonical document-index parser for target rows and reject ambiguity/year-only values.
- Safe quantity packages need one exact normalized unit or an explicit tested conversion; UNKNOWN
  units remain manual.
- Inspect formula and cached-value views together. An eligible formula without a cache must create
  a controlled source issue, not silently reduce checked coverage.
- Reject duplicate source SHA before job creation (recommended) or define explicit deduplication
  and checked-file semantics. Two equal uploads currently produce 26 rows and 13 two-member groups
  from a 13-row source.

## Reconcile-specific integrity gaps

- RA-005: validate a complete prospective decision snapshot and install it atomically.
- RA-006: publish and verify output before feedback commit, or compensate transactionally.
- RA-007: reject target `.xlsm` until macro/VBA/signature-safe selected and no-change contracts exist.
- RA-008: unlink post-publish output only while its captured inode still matches.
- RA-009: globally reserve selected physical source identity before calculation/write.
- RA-010: fail closed on duplicate `(index, category)` until stable target-row identity is approved.
- RA-013: reject negative-pair endpoints absent from the materialized group set or remove the inert API.

## Verified positive boundaries

- Representative source and target inputs remained byte-identical through every audit run.
- One independently traced unaffected cumulative row preserved formula caches and exact Decimal
  coefficient/rounding behavior through the verified adjacent reconcile output.
- The successful audit-only red annotation changed only styles and the intended worksheet part;
  all cell formulas, values and data types remained identical.
- Focused and full regression suites are green, but real-data verification tests are opt-in and the
  unit fixtures do not cover the failing real style structure or alternate cumulative header.

## Remediation order

1. Owner decisions: RA-014 numeric meaning and RA-017 stage selection.
2. Fail-closed ingestion: RA-001, RA-002, RA-003 and RA-011.
3. Guaranteed safe artifact: RA-015 and RA-018.
4. Unit and duplicate boundaries: RA-004 and RA-016.
5. Adjacent reconcile exact-once/transaction/publication: RA-006 through RA-010.
6. Restart recovery and latent contracts: RA-005, RA-012 and RA-013.
