---
type: error-catalog
status: closed
tags:
  - knowledge/error
  - domain/document-processing
  - capability/admin-panel
  - risk/high
last_verified: 2026-08-16
updated: 2026-08-16
source_paths:
  - src/report_processor/admin_panel/reconciliation_*
  - src/report_processor/admin_panel/service.py
  - src/report_processor/reconciliation_grouping
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - src/report_processor/work_semantics
---

# Reconciliation and verification accuracy findings

This is the de-identified closure record for
[[../tasks/reconciliation-max-accuracy-audit-v1|the maximum-accuracy audit]]. Source code and tests
remain authoritative. Closure means each known finding has an implemented guard or an explicit
fail-closed boundary; it does not assert perfect accuracy for every future workbook.

## Current status

| Findings | Status | Accepted boundary |
| --- | --- | --- |
| RA-001, RA-002, RA-011, RA-019 | closed | region-first source discovery, semantic detail rows, exact merged ancestry, shared role resolution, formula/cache pairing, controlled ambiguity |
| RA-003, RA-004, RA-020 | closed | canonical terminal identity, exact-unit safety, unique selected-stage intersection |
| RA-005, RA-006, RA-009, RA-010, RA-012 | closed | immutable decisions, exact-once apply, duplicate-target rejection, transactional feedback, restart recovery |
| RA-007, RA-008, RA-018 | closed fail-safe | unsupported macro policy, inode-bound cleanup, descriptor-bound no-clobber publication |
| RA-013, RA-016 | closed | dangling-pair rejection and physical source identity guards |
| RA-014 | closed | numeric oracle uses the structurally selected target pair and common writer quantization |
| RA-015 | closed | namespace-aware/styles-safe OOXML writing and package verification |
| RA-017 | closed | explicit or uniquely discovered target stage; no hidden stage fallback |
| RA-021 | closed | explicit reconcile-only period, virtual preview, actionable insertion, UI/API wiring, semantic identity v2, manifest v4 |

## Source-layout closure

The original defect came from discovering work/unit roles globally and independently of metric
regions. Real hierarchical headers could silently fall back from cumulative to direct semantics or
cross into a later table. The accepted source reader now:

- discovers every physical adjacent quantity/total-cost seed across the sparse sheet;
- follows exact nested and merged ancestry and keeps immutable detail intervals;
- resolves work/unit roles only from local non-price lineages through the shared schema resolver;
- validates row-producing layouts before uniqueness and retains cumulative precedence;
- keeps formula coordinates separate from cached numeric values;
- fails controlled ambiguity instead of choosing by position, row cutoff, or wording score;
- bounds cells, merges, candidates, probes, and aggregate visits without using inflated worksheet
  dimensions.

Styled empty cells are ignored as semantic evidence and do not consume the relevant-coordinate
limit. Actual values, formulas, and merges still count. The final private shadow accepted nine
sources and retained three as continuable controlled ambiguities; no financial output was guessed.

## Target, period, and semantic closure

Target roles are header-authoritative. A content fallback exists only when document-index and stage
are jointly missing while row/work/unit roles are already uniquely bound; one exact shared anchor
set and valid detail blocks are required. Physical header discovery is independent of the selected
stage, so later stages do not hide the actual metric header.

Current and historical quantity/cost pairs are recognized structurally. Monetary labels use
`UnitOntology-1.1` and `ReportingScope-2.1`: a full canonical unit proves a rate, a bounded shared
reporting grammar proves a total, and mixed or unknown evidence is rejected. These semantics enter
`ReconciliationTargetIdentity-2.0`, which also binds target-measure and term-canonicalization
versions. `AdminReconciliationJobManifest-4.0` rejects stale v3 evidence before writer or feedback
replay.

An explicit `YYYY-MM` is accepted only for reconcile. Preview is read-only; verification never
calls the planner or transformer. Physical insertion happens only after immutable decisions and an
actionable calculation. Threaded-comment support is bounded to exact safe relationships, person
records, timestamps, references, and XML topology.

## Writer and archive closure

The namespace-aware writer uses immutable byte spans, same-handle ZIP admission, descriptor-bound
snapshots, exact output hashing, formula-result ownership, and no-clobber publication. It rejects
unsafe encodings, DTD/entities, ambiguous cells/formulas/values, excessive archive/XML resources,
signatures, and raced identities.

Period insertion additionally preserves validated source `ZipInfo` metadata. Raw local-header
flags must match central-directory flags and the compression-method allowlist; LZMA requires its EOS
flag. The metadata-preserving writer deliberately follows a bounded CPython private implementation,
so a Python standard-library upgrade requires focused revalidation.

## Final evidence

- Sequential private shadow: 12 sources plus one target, one uniquely selected stage, 2,787 source
  rows, 984 visible review rows, three continuable ambiguities, no output, no apply, all 13 inputs
  byte-identical.
- Focused release profile: `581 passed, 1 skipped`.
- Full repository: `2225 passed, 25 skipped` in `28.07s`; skips were explicit opt-ins.
- Ruff check, Ruff format check, and diff check passed.
- Independent source and service reviewers returned `MERGE YES` with no P0/P1 finding.

## Retained fail-closed policy

- Multiple viable source layouts, target stages, target rows, periods, or role bindings remain
  controlled failures.
- Unknown units, mixed semantic scope, missing formula cache, unsupported OOXML topology, stale
  manifests, and resource-limit excess never produce `passed` or an output.
- Original workbooks are never modified. Review alone never exposes a result, and apply requires
  all unresolved rows to be decided explicitly.
- Do not add private-template aliases, coordinate fallbacks, or test deletions to make a difficult
  workbook pass.
