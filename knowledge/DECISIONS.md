---
type: decisions
tags:
  - knowledge/decision
last_verified: 2026-07-27
updated: 2026-07-27
---

# Decisions

Record only accepted cross-cutting decisions. Link each decision to affected component cards and tasks; do not duplicate implementation detail here.

## Accepted

- Script-first deterministic core; GPT optional/default-off and never numeric authority or file selector. [[components/document-reconciliation|Component card]]
- Immutable import, SHA-256 lineage, Decimal calculations, atomic copy export with reopen/manifest verification. [[components/document-reconciliation|Component card]]
- CodeGraph deferred until first Python/TypeScript scaffold; then non-production `codegraph init`; `.codegraph/` remains local index. [[components/document-reconciliation|Component card]]
- Model access does not require API: disabled, local GPT-capable CLI and manual strict-JSON GPT-application bridge are supported plan modes; an API adapter is optional. [[components/document-reconciliation|Component card]]
- MVP supports XLSX and folder/ZIP inputs; XLSB is an explicit blocker and post-MVP adapter, never a silent partial import. [[components/document-reconciliation|Component card]]
- Implementation orchestration targets an explicitly authorised xhigh project profile; profile configuration/restart is a pre-P1 setup gate, not part of the current planning-only work. [[components/document-reconciliation|Component card]]

## Pending owner approval (Gate 0)

- The values listed in [BUSINESS_RULES §7](../docs/BUSINESS_RULES.md) are blockers, not accepted defaults: M04/M05 exact include sets, M13/M14, suffix/supporting-work semantics, stage/month/whole-period/quantity, 2.7, J/L tolerance, units, versions, formula freshness, feedback policy and AI context/token budget. M02/M06 literals are accepted. [[components/document-reconciliation|Component card]]
- Feedback will be versioned memory rather than online training; exact reuse/retention/threshold values remain owner decisions. [[components/document-reconciliation|Component card]]
