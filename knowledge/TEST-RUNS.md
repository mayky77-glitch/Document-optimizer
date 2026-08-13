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

## 2026-08-13 — structural target-measure Wave 2

- Feature tip `57a56efa7621e3d65277e6117e033a6718094f1f`; accepted ORDA integration
  `1362c538bbb81fdb5d16e5617cd4f9a55cb01632`; published checkpoint `959e3b9`.
- The exact focused target/execution/verification/recovery profile completed with `104 passed` on
  the feature integration and canonical `main`. Ruff, format and diff checks passed.
- Independent P6 review reproduced month-only and month+year identities, March/May disambiguation,
  multi-period/conflicting evidence rejection, historical-scope rejection, exact error propagation
  and discovered-cell-only writing. Merge verdict: yes.

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
