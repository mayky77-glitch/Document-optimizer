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

## 2026-08-13 — period-insertion feature P6 rejection

- Feature tip `dd3273e246ffee69c635a19f85a01339c91ee2ab` passed its narrow profile (`24
  passed`, Ruff/format/diff clean) but failed independent P6 and remains unmerged.
- Small synthetic repros proved that the verifier accepted a changed old cell value; conditional
  formatting `sqref`, auto-filter relative IDs, inherited calcChain sheet identity, hyperlinks,
  row/column layout and inter-sheet formulas were not handled safely. New inserted columns also did
  not clone effective widths.
- The result is a controlled remediation, not test expansion or a private-data exception: bind an
  immutable plan/preflight first, then require full inverse-delta comparison and fail closed for
  every unsupported coordinate-bearing structure.

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
