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
  Owner approved a numeric oracle and automatic single-stage selection in
  [[DECISIONS#DO-017: «Проверка документов» получает числовой oracle (2026-08-13)|DO-017]] and
  [[DECISIONS#DO-018: этап цели выбирается без скрытого значения (2026-08-13)|DO-018]].
- [[tasks/admin-verification-lifecycle-gate0|Lifecycle Gate 0]] is accepted: transactional
  exact-once apply and restart/pruning recovery are integrated at `c8da710`.
- Original/reference comparison supersedes the fixed-column clause through
  [[DECISIONS#DO-019: числовая пара цели определяется структурой, а не адресом (2026-08-13)|DO-019]].
  [[tasks/reconciliation-real-layout-gate0|Real-layout Gate 0]] freezes the remaining structural
  source, target-oracle and period-insertion waves.
- [[tasks/reconciliation-real-layout-source-identity|Structural source/identity Wave 1]] is
  accepted and published at `fe3d5ee`: exact merged-parent binding, broad structural work-header
  nomination and unique 3/4-digit source-to-stage identity are enforced without positional or
  narrow-phrase fallback.
- [[tasks/reconciliation-real-layout-target-measure|Structural target-measure Wave 2]] is accepted
  through ORDA integration `1362c53` and published at `959e3b9`. Verification now reads only one
  structurally proven current-period quantity/cost pair; a historical-only target fails with an
  exact technical code and produces no red artifact.
- [[tasks/reconciliation-period-insertion-gate0|Reporting-period insertion Gate 0]] freezes two
  sequential low-load waves: a direct OOXML transformer, then preview/apply integration. The
  insertion is reachable only from reconciliation with an explicit `YYYY-MM` period and only when
  at least one calculated value will be written.
- The first OOXML feature tip `dd3273e` is not accepted. Independent P6 review reproduced unsafe
  inverse verification, formula/range translation and column/filter/calcChain defects. Remediation
  is deliberately split into plan/preflight integrity and exact transform/verifier work; no private
  corpus or full-suite run is allowed inside either low-load substep.

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

Remediate [[tasks/reconciliation-period-ooxml|the frozen OOXML transformer card]] from published
base `f024d16`: first bind a digest-stable structural plan and fail-closed preflight, then implement
and independently verify the exact OOXML inverse delta. Do not integrate `dd3273e`, open the
dependent preview/apply card, or start the service/API/UI period field before P6 accepts the
transformer.
