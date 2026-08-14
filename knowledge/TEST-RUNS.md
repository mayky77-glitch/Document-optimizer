---
type: test-runs
tags:
  - knowledge/component
  - domain/document-processing
last_verified: 2026-08-15
updated: 2026-08-15
---

# Test runs

Keep only the two latest completed runs relevant to active work.

## 2026-08-15 — namespace-aware writer v3 accepted

- Feature `d71b7f43c72493ef7c77de9a278f27ad453274da`, ORDA integration `206fcbb` and
  main integration `fee01c4` passed the exact low-load frozen profile: `159 passed` in about two
  seconds on both feature and main-based integration; Ruff check/format and `git diff --check`
  passed.
- Independent ordinary and security reviews returned `MERGE YES`. Regressions cover exact output
  SHA, descriptor reads from offset zero, formula result adoption, post-replace `BaseException`
  cleanup, raced no-clobber links, strict UTF-8 worksheet bytes, ZIP/ZIP64 boundaries, DTD/entities,
  duplicate cells/children, custom worksheet size limits and controlled error-code preservation.
- No private workbook or full suite was used in this bounded wave. Those remain deferred to the
  single final release shadow after API/UI wiring.

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

## Knowledge validation

Global validator remains `INVALID` because many historical task cards predate the current schema.
New and changed cards/links are checked separately; historical vault migration is outside this
accuracy remediation.
