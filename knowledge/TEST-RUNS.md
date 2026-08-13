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

## 2026-08-13 — structural source/identity Wave 1

- Feature `1860741e5cf0bb9e38e01a55a1376a876c9c85b8`; accepted ORDA integration `3364bb3`;
  published `main` checkpoint `fe3d5ee`.
- Focused command is the exact source/target/execution/real-data profile frozen in
  [[tasks/reconciliation-real-layout-source-identity|the task card]].
- Result after feature, integration and canonical-main merge: `37 passed, 1 skipped`; the skip is
  the explicit private-corpus test. Ruff, format and diff checks passed.
- Independent P6 review returned merge yes with no blockers and separately reproduced exact merge
  binding, broad work-role selection and unique three-digit parenthetical stage intersection.

## 2026-08-13 — real target/reference shadow

- Twelve original sources, one clean target and one desired reference were inspected from immutable
  copies; every input hash stayed unchanged. OOXML contains 1,820,820 formula cells and a `<v>`
  node for each, but 1,196 caches are empty. Only a formula in an otherwise eligible reconciliation
  metric row is a controlled failure; blanket workbook-level rejection would be inaccurate.
- Clean/reference comparison: 180 rows in both; width 15→17; J/K unchanged; one adjacent
  reporting-period pair appears in L/M; the narrative block shifts two columns right; only the
  selected stage gains period values.
- Current runtime cannot complete this shadow: merged-header candidate construction reports false
  ambiguity and the valid full dotted target identifier is rejected. These are RA-019—RA-021 in
  [[tasks/reconciliation-real-layout-gate0|Real-layout Gate 0]].

## Knowledge validation

Global validator remains `INVALID` because many historical task cards predate the current schema.
New and changed cards/links are checked separately; historical vault migration is outside this
accuracy remediation.
