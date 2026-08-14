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

## 2026-08-14 — wholly-left shared formulas accepted

- Feature `d06bab74de77338921d801d9fc470412e7f96c39`, ORDA integration `2e28152` and
  published main `90e7a73` passed the exact low-load profile: `86 passed` in `0.57s`; Ruff
  check/format and `git diff --check` passed.
- Independent P6 reproduced invalid blank/overflow IDs, incomplete/reused/overlapping groups,
  forged plan evidence and a duplicate formula-less physical `<c>` at anchor/follower addresses.
  Forward preflight and the separate verifier-local parser reject every case; a unique adjacent
  cell remains valid and failed preflight preserves a pre-existing output sentinel.
- No private workbook or full suite was used in the feature task. The final real shadow remains
  deferred until apply/service/API wiring is complete.

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

## Knowledge validation

Global validator remains `INVALID` because many historical task cards predate the current schema.
New and changed cards/links are checked separately; historical vault migration is outside this
accuracy remediation.
