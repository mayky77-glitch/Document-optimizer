---
type: error-catalog
status: in_progress
tags:
  - knowledge/error
  - domain/document-processing
  - capability/admin-panel
  - risk/high
last_verified: 2026-08-12
updated: 2026-08-12
source_paths:
  - src/report_processor/admin_panel/reconciliation_*
  - src/report_processor/reconciliation_grouping
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/excel_writer
---

# Reconciliation accuracy findings

This catalog is the authoritative de-identified handoff for
[[../tasks/reconciliation-max-accuracy-audit-v1|the active maximum-accuracy audit]].
Code, tests and direct workbook evidence override this note.

## Finding matrix

| ID | Severity | Boundary | Deterministic result | Corpus exposure |
| --- | --- | --- | --- | --- |
| RA-001 | critical | source classification | cumulative KS-6a is selected as KS-2 and contract metrics reach output | confirmed in representative corpus |
| RA-002 | high | source row boundary | a valid first data row can be skipped by fixed `leaf + 2` | synthetic; current corpus has number rows |
| RA-003 | high | target index | trailing four-digit year can replace the document index | synthetic; absent in current target |
| RA-004 | high | unit/package safety | mixed exact units or distinct unknown units can be mass-safe | synthetic |
| RA-005 | high | decision persistence | mixed-scope autosave cannot restore on recreated state | synthetic |
| RA-006 | high | lifecycle transaction | failed apply can persist feedback without a result | synthetic |
| RA-007 | high | target format | `.xlsm` is accepted but selected writes fail; no-change output is mislabeled | synthetic contract path |
| RA-008 | high | writer cleanup | post-publish failure can delete a concurrent replacement | synthetic |
| RA-009 | high | exact-once calculation | one source row can contribute more than once | synthetic |
| RA-010 | medium | target catalog | duplicate index/category silently overwrites the earlier target row | synthetic; absent in current target |
| RA-011 | medium | formula cache | formula metrics without cached values disappear without a source issue | synthetic; none in audited metrics |
| RA-012 | medium | service restart | ready results and review jobs are stranded after process restart | synthetic lifecycle |
| RA-013 | medium | hard constraints | dangling negative-pair references are ignored | synthetic API contract; no current caller found |

## RA-001 — cumulative source selected as contract-detail source

### Root cause

`_extract_ks6a_rows` recognizes only a work header containing `наименование этапа`.
One structurally cumulative workbook instead uses a valid work/cost wording. Its explicit
`выполнено за весь период` anchor and adjacent cumulative quantity/cost leaves are present,
but the KS-6a extractor returns no rows. `_extract_one` then falls back to the generic KS-2
extractor, which binds an earlier contract quantity/cost pair and also accepts a displayed
column-number row as data.

### Reproduction and effect

- Production selection: `ks2`, 13 rows, no issue.
- Correct cumulative interpretation: 12 rows.
- Fallback totals: quantity `744.685`, cost `5,219,927` RUB.
- Cumulative totals: quantity `171.47`, cost `311,553.59` RUB.
- An isolated authoritative apply accepted one affected row. The source contract pair was
  `32` and `2,874,875` RUB while its cumulative pair was `0` and `0`; the result published
  `32.00` and `7.76` million RUB in the target cells.

This is direct wrong-output evidence and blocks any 100% accuracy claim.

### Safe fix contract

Evaluate structural layout candidates instead of first-success token matching. A cumulative
candidate needs a normalized work-header alias, strict unit header, explicit cumulative anchor
and adjacent quantity/total-cost leaves bound to that anchor region. Find the first detail row
semantically (nonnumeric work, textual unit, finite pair), skipping display-number rows. A valid
cumulative candidate wins over a generic KS-2 pair; incompatible multiple candidates fail with
a controlled ambiguity. Add a regression with the alternate header, distant cumulative pair,
number row, exact 12-row result and cumulative totals.

## RA-002/003/010/011 — ingestion and target guards

- `leaf_row + 2` silently drops the first data row when a two-row merged header has no number
  row. Changing it blindly to `+1` would ingest number rows in the current corpus; the start
  boundary must use the semantic detail predicate from RA-001.
- `terminal_index` chooses the final four-digit run, so an index followed by a year resolves to
  the year. Use the canonical document-index parser and reject ambiguity/year-only values.
- `_catalog` uses last-write-wins for duplicate `(index, category)`. Fail closed until a stable
  row-identity policy is owner-approved.
- Source workbooks are opened `data_only=True`; a formula metric without a cache becomes `None`
  and the row is skipped. Inspect formula/cache views together and surface a controlled issue.

## RA-004/013 — grouping safety

Mass-safe packaging uses unit family, not exact normalized unit. `м` and `км` can be accepted
together; calculation then drops mismatched quantity while still applying cost. Distinct
unrecognized units also collapse to `UNKNOWN` and can be mass-safe. Safe `quantity_cost`
packages need one exact normalized unit or an explicit tested conversion contract; unknown
units stay manual. Constraint validation must also reject negative-pair endpoints absent from
the materialized group set.

## RA-005/006/012 — decisions and lifecycle

- Saved group/row versions include all decision maps. Restore validates those versions before
  installing saved package/family maps, so valid mixed-scope snapshots look stale and are
  discarded. Validate a prospective complete snapshot and install it atomically.
- Apply orders output creation, feedback commit, output chmod and ready state. A failure after
  feedback commit removes the output but leaves durable feedback. Finalize/verify permissions
  before publishing feedback, or use an application transaction with compensation.
- Jobs exist only in memory. A new service instance cannot download an on-disk ready result or
  reach a review autosave, and no retry route exists. Add a durable minimal manifest/recovery
  contract or explicitly remove restart expectations and orphaned directories.

## RA-007/008 — publication contract

- Reconciliation upload accepts a target `.xlsm` and review can be prepared, but selected apply
  calls a writer that accepts only `.xlsx`, producing `INVALID_SOURCE`. No-selected apply copies
  macro-enabled bytes into `result.xlsx`, creating an extension/content-type mismatch. Until a
  macro/VBA/signature-safe output contract exists, fail closed for target `.xlsm` at upload.
- After publishing an XLSX, writer cleanup unlinks the output on reopen failure using only a
  boolean flag. If another actor replaced the path, that replacement is deleted. Capture the
  published inode and unlink only if identity still matches.

## RA-009 — exact-once boundary

Matching/calculation does not globally reserve selected `source_row_id`. One source can be
selected for two targets, and distinct candidate IDs for the same source can be selected inside
one match. Both paths duplicate arithmetic. Quality control can detect one downstream shape,
but authoritative admin apply calls calculation and then writer with `ALLOW_WRITE` without QC.
Reject duplicate selected source identity before calculation/write and cover both shapes.

## Verified positive boundaries

- Representative run kept all 12 inputs byte-identical and produced one verified result.
- One independently traced unaffected row used cumulative formula caches `20.26398` and
  `1,807,448.33` RUB; coefficient `2.7` published `20.26` and `4.88` million RUB.
- Target/result comparison found exactly two non-formula value changes in the accepted row.
  All 94 original target formulas were materialized as numeric values, with only calc-chain
  package metadata removed as designed.
- The audited target has 87 unique `(index, category)` keys, no duplicate keys and no ambiguous
  four-digit index rows.
- Audited metric cells contained 30,755 formulas with cached numeric values and zero missing
  caches. This does not excuse RA-001: formula counting is not structural source classification.

## Regression suite required for remediation

1. Real-layout KS-6a alias/cumulative precedence and semantic data start.
2. Formula-without-cache controlled issue.
3. Ambiguous/year index and duplicate catalog fail-closed.
4. Exact normalized unit and UNKNOWN-unit mass-safety rejection.
5. Global selected source exact-once.
6. Mixed-scope autosave restore and service restart recovery.
7. Post-commit feedback failure compensation.
8. `.xlsm` selected/no-selected target behavior.
9. Concurrent replacement survival during writer cleanup.
