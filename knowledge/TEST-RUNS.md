---
type: test-runs
tags:
  - knowledge/component
  - domain/document-processing
last_verified: 2026-08-13
updated: 2026-08-13
---

# Test runs

Keep only the two latest completed runs relevant to active work.

## 2026-08-13 — period-insertion A accepted, B rejected

- Plan/preflight tip `fb5d1aaa24479f1ce3f3bb97a636e743fdc27d12` passed independent P6-A:
  canonical source-rebuilt plan digest, broad nested historical ancestry, bounded compact suffix
  evidence, calendar equivalence/conflict and fail-closed preflight. Focused profile: `34 passed`.
- Transform tip `5eb87b9c8827970076cdd32588739fddb8f17e3a` passed its narrow `40 passed`
  profile but failed independent P6-B and remains unmerged. Synthetic tampering of dimension,
  merge, width, row spans, conditional-format range, extra/missing cells and unrelated workbook
  attributes passed the partial verifier. A forced post-link hash failure also reported failure
  while leaving an output published.
- Remediation requires complete independent inverse-tree comparison, a no-fallible-work-after-link
  boundary and exact supported handling for filter database, print titles, left comments/VML,
  left hyperlinks, strict formula tokens and sheetId-bound calcChain.

## 2026-08-13 — low-load period-insertion architecture shadow

- Twelve original sources, one clean target and one desired reference were inspected from immutable
  copies; every input hash stayed unchanged. OOXML contains 1,820,820 formula cells and a `<v>`
  node for each, but 1,196 caches are empty. Only a formula in an otherwise eligible reconciliation
  metric row is a controlled failure; blanket workbook-level rejection would be inaccurate.
- Clean/reference comparison still proves an adjacent two-column reporting-period insertion while
  the historical pair and all mapped values remain unchanged. The mapped formulas follow exact A1
  insertion translation; the sole additional formula is a calculated cost value on one semantic
  row, not a structural formula the insertion layer must invent.
- Both packages contain the same 16 ZIP members. The actual coordinate-bearing surface includes
  formulas/calcChain, 64 merges, 22 conditional-format ranges, one auto-filter, one simple defined
  name and comments/VML. No tables, charts, external links, validation or extension lists were
  present. Source hashes stayed unchanged.
- A bounded `openpyxl.insert_cols()` probe demonstrated why it is not an implementation option: it
  does not translate the full coordinate graph and rewrites package state. The frozen implementation
  uses direct OOXML plus an independent inverse-delta verifier.

## Knowledge validation

Global validator remains `INVALID` because many historical task cards predate the current schema.
New and changed cards/links are checked separately; historical vault migration is outside this
accuracy remediation.
