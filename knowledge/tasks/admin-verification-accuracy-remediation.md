---
type: task
status: draft
card_id: admin-verification-accuracy-remediation
version: 1
work_id: admin-verification-accuracy-remediation-v1
task_id: integration
purpose: Remediate evidence-backed verification accuracy and publication failures after owner decisions.
role: worker
agent_role: orchestrator
owner: unassigned
profile: L3
routing_grade: P6
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: planned
source_base_sha: 7aa8d30e5abbd49b6d5b9e76b03122c0f447f51e
write_scope: []
tags:
  - task/planning
  - status/draft
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[../components/document-verification|Проверка документов]]"
  - "[[../errors/reconciliation-accuracy-findings|Каталог ошибок]]"
  - "[[../research/propextract-methods-2026-08-13|PropExtract methods]]"
---

# Verification accuracy remediation

No production work starts from this card until the owner answers two product questions:

1. Does “Проверка документов” promise numeric quantity/cost equality, or only recognized
   classification/membership? If numeric, approve measures, aggregation, unit conversions,
   coefficients, rounding and tolerance.
2. How is target stage selected: explicit UI choice, safe single-stage discovery, or strict default?

After those decisions, use dependency waves:

- Wave 1: structural source candidate selection, semantic data start, dual formula/cache guard,
  canonical target index and empty/ambiguous target-scope rejection.
- Wave 2: numeric oracle (if approved), exact-unit safe boundary and duplicate-SHA policy.
- Wave 3: robust raw OOXML style child scan, post-patch reopen and ownership-safe multi-source ZIP
  publication.
- Wave 4: real-layout regression fixtures, representative private shadow run, focused/full gates
  and independent P6 acceptance.

Use [[../research/propextract-methods-2026-08-13|PropExtract]] only as a methodology reference:
exact-or-ambiguous identity, field-level provenance, order-independent consensus, narrow
normalization, staged workbook delta allowlists and permutation tests. Its code is not licensed for
copying and its PDF/OCR/domain rules are not this feature's contract.

Acceptance requires zero silent row loss, no false clean result, no false red rows in the frozen
layout regression, source/target digest preservation, a downloadable real-workbook artifact and
an explicit statement of what `passed` proves.
