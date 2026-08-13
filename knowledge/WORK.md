---
type: work
tags:
  - knowledge/component
  - domain/document-processing
  - status/in-progress
last_verified: 2026-08-13
updated: 2026-08-13
---

# Work

## Current

- [[tasks/admin-verification-accuracy-remediation|Verification accuracy remediation]] is active.
  Owner approved a numeric J/K oracle and automatic single-stage selection in
  [[DECISIONS#DO-017: «Проверка документов» получает числовой oracle (2026-08-13)|DO-017]] and
  [[DECISIONS#DO-018: этап цели выбирается без скрытого значения (2026-08-13)|DO-018]].
- [[tasks/admin-verification-remediation-gate0|Gate 0]] freezes dependency waves, private-data
  boundaries and exact acceptance gates. Baseline at `dc2c321` is `1667 passed, 25 skipped`.

## Completed context

- [[tasks/reconciliation-max-accuracy-audit-v1|Maximum-accuracy verification/reconciliation
  audit]] completed without production changes. It independently compared immutable workbook
  copies, rejected the 100% accuracy claim and catalogued RA-001 through RA-018 in
  [[errors/reconciliation-accuracy-findings|the evidence-backed handoff]].
- [[tasks/reconciliation-global-batch-review-v5-final|Global batch review v5]] established
  authoritative row/group/package decisions and verified XLSX publication.
- [[tasks/reconciliation-real-data-resilience-v4-final|Real-data resilience v4]] established
  independent source failure handling and opaque public identities.

## Next executable step

Publish the Gate 0 planning SHA, run Wave 1 in three non-overlapping worktrees, integrate with
`--no-ff`, then open the numeric/stage wave only from the accepted integration SHA.
