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
- Units are resolved by semantic headers, not fixed letters: observed Table-2 F is compared per row with observed Table-1 J even if either column shifts. A mismatch makes the Table-2 unit cell red and appends the source unit after `/`. [[components/document-reconciliation|Component card]]
- Physical quantity sums only approved rows whose normalized unit matches Table 2 unless a conversion is explicitly approved. Monetary cost sums every approved row even when its unit differs; the mismatch remains visible and auditable. [[components/document-reconciliation|Component card]]
- If Table 1 has no process-name candidate at all, both derived quantity and cost are `0`. Candidate rows are shown with a direct preselected **«Учитывать»** checkbox, contribution, uncertainty and optional comment; user changes trigger deterministic recalculation. [[components/document-reconciliation|Component card]]
- Quantity uses the Table-2 unit first. If only one alternative source unit exists, its approved quantities are summed and marked red `old/source`; if several exist, separate unit subtotals are shown and the user selects one group. Different units are never added together; cost still includes all approved rows. [[components/document-reconciliation|Component card]]

## Pending owner approval (Gate 0)

- The values listed in [BUSINESS_RULES §7](../docs/BUSINESS_RULES.md) are blockers, not accepted defaults: M04/M05 exact include sets, M13/M14, suffix/supporting-work semantics, stage/month/whole-period/quantity, 2.7, J/L tolerance, automatic unit conversion, versions, formula freshness, feedback policy and AI context/token budget. No-process `0/0`, checkbox review and alternative-unit grouping are accepted with the prior unit/cost rules. [[components/document-reconciliation|Component card]]
- Feedback will be versioned memory rather than online training; exact reuse/retention/threshold values remain owner decisions. [[components/document-reconciliation|Component card]]
