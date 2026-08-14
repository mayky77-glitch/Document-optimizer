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
- Direct OOXML insertion is accepted through feature `0740109`, ORDA integration `f236291` and
  published main checkpoint `991002a`. Its source-rebuilt plan, full inverse semantic verifier,
  stable ZIP metadata proof, left comments/VML/external hyperlinks and no-clobber publication all
  passed the final independent P6 and a `56 passed` focused gate.
- [[tasks/reconciliation-period-shared-formulas|Shared-formula preservation]] is accepted through
  feature `d06bab7`, ORDA integration `2e28152` and published checkpoint `90e7a73`. Complete
  unchanged groups wholly left are preserved; uint32/blank IDs, duplicate physical cells,
  incomplete/affected topology, array and data-table groups fail closed under an independent
  verifier-local parser.

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

Implement [[tasks/reconciliation-period-preview-complete|the combined bounded preview card]]. The
earlier six-file scope produced checkpoint `88bb456` and 122 focused passes, but independent P6
proved that historical planning still inherited a rectangular `max_column` scan from the shared
detector. The replacement card owns that shared boundary explicitly rather than hiding it with a
monkeypatch. Then run [[tasks/reconciliation-period-apply-service-v2|transactional apply/recovery]].
Verification stays strict/no-write; API/UI wiring remains separate. Run the private release shadow
and full suite only once after the complete write path is integrated.
