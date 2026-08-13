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

## 2026-08-13 — direct OOXML period insertion accepted

- Final feature `07401099c25898eef14ad6fcf2703040391dbdb9`, ORDA integration `f236291` and
  published main checkpoint `991002a` passed the exact low-load profile: `56 passed` in `0.32s`
  on canonical main; Ruff check, Ruff format and `git diff --check` passed.
- Independent P6 re-ran the prior adversarial cases. Whole-tree inverse verification rejected
  unrelated workbook, calcChain, drawing, worksheet and ZIP-metadata changes. Doubled-quote A1
  formulas translated correctly; whole-row/column, dynamic, cross-sheet and unsupported formulas
  failed closed. Wholly-left comments/VML/external hyperlinks remained byte-identical, while
  affected variants were rejected.
- Publication performs every fallible proof before the final hard-link. A pre-existing sentinel
  survives, pre-link failure publishes nothing and post-link best-effort cleanup cannot turn a
  valid published result into a reported failure.
- Full and private runs were deliberately deferred to the final release shadow to limit system
  load. The actual clean target still needs the separate wholly-left shared-formula compatibility
  gate before it is an eligible end-to-end insertion input.

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
