---
type: task
status: in_progress
card_id: admin-verification-accuracy-remediation
version: 2
work_id: admin-verification-accuracy-remediation-v1
task_id: integration
purpose: Remediate evidence-backed verification accuracy and publication failures after owner decisions.
role: worker
agent_role: orchestrator
owner: integration-owner
profile: L3
routing_grade: P6
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: planned
source_base_sha: dc2c32131face777f4cd3f4e121181e609154ed8
write_scope: []
tags:
  - task/planning
  - status/in-progress
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[../components/document-verification|Проверка документов]]"
  - "[[../errors/reconciliation-accuracy-findings|Каталог ошибок]]"
  - "[[../research/propextract-methods-2026-08-13|PropExtract methods]]"
---

# Verification accuracy remediation

Owner decisions are accepted in [[../DECISIONS#DO-017: «Проверка документов» получает числовой oracle (2026-08-13)|DO-017]]
and [[../DECISIONS#DO-018: этап цели выбирается без скрытого значения (2026-08-13)|DO-018]].
Implementation uses dependency waves frozen by
[[admin-verification-remediation-gate0|Gate 0]]:

- Wave 1: structural source/target safety, grouping/state safety, and OOXML/ZIP publication.
- Wave 2: numeric oracle plus stage/API/UI integration and adjacent target-writer safety.
- A separate accepted integration SHA opens lifecycle/transaction remediation for remaining
  adjacent `reconcile` findings, then real-layout shadow checks and independent P6 acceptance.

The lifecycle wave is frozen in [[admin-verification-lifecycle-gate0|Lifecycle Gate 0]]: first
[[admin-verification-apply-integrity|transactional apply]], then dependent
[[admin-verification-job-recovery|restart recovery]].

That lifecycle is accepted at `c8da710`. A subsequent original/reference comparison proved the
fixed J/K target clause wrong for the designated template and opened
[[reconciliation-real-layout-gate0|Real-layout Gate 0]] under DO-019.

Use [[../research/propextract-methods-2026-08-13|PropExtract]] only as a methodology reference:
exact-or-ambiguous identity, field-level provenance, order-independent consensus, staged workbook
delta allowlists and permutation tests. Do not adopt its narrow comparison normalization: source
header recognition stays universal across variable hierarchical multi-row wording. Its code is not
licensed for copying and its PDF/OCR/domain rules are not this feature's contract.

Acceptance requires zero silent row loss, no false clean result, no false red rows in the frozen
layout regression, source/target digest preservation, a downloadable real-workbook artifact and
an explicit statement of what `passed` proves.
