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
- Coefficient `2.7` is an average heuristic used only for a review check: `(Table1 cost in million RUB) × 2.7 >= Table2.K` is OK; a lower result is highlighted for inspection with both values and their difference. It never changes the exported Table-1 cost. [[components/document-reconciliation|Component card]]
- The coefficient is one run-level editable field with default `2.7`, never per-row. A failed check is orange and non-blocking after explicit acknowledgement; coefficient and acknowledgement are saved in manifest/audit. [[components/document-reconciliation|Component card]]
- Table-2 J/L are compared numerically after rounding both to two decimal places. Exact post-rounding equality is yellow; textual formatting and trailing zeros do not matter, and `0 = 0` is yellow. [[components/document-reconciliation|Component card]]
- For J/L highlighting, blank/blank is also treated as unchanged and yellow; blank/number is not equal and is not yellow. Blank is never coerced to zero. [[components/document-reconciliation|Component card]]
- Aggregations and coefficient checks retain full Decimal precision. Only final quantity/cost output and J/L comparison values are rounded to two decimals with `ROUND_HALF_UP` (`1.234 → 1.23`, `1.235 → 1.24`); manifest keeps exact and rendered values. [[components/document-reconciliation|Component card]]
- The selected month uses one semantic quantity/cost column pair. Missing pair is appended at the right with copied report structure/styles; an existing pair is reused without duplication. Nonblank values show old→new and require explicit overwrite confirmation. [[components/document-reconciliation|Component card]]
- User receives exactly one standalone Table-2 XLSX. Table 1 contributes saved values only; no formula is copied. Existing Table-2 formulas are flattened to saved visible values, new results are numeric, and verified output has zero formulas/external links while retaining styles/colors/editability. Internal manifest/audit remains local. [[components/document-reconciliation|Component card]]

## Pending owner approval (Gate 0)

- The values listed in [BUSINESS_RULES §7](../docs/BUSINESS_RULES.md) are blockers, not accepted defaults: M04/M05 exact include sets, M13/M14, suffix/supporting-work semantics, stage/month/whole-period validation, automatic unit conversion, versions, missing cached-value recovery, feedback policy and AI context/token budget. Standalone value-only output and prior calculation/review rules are accepted. [[components/document-reconciliation|Component card]]
- Feedback will be versioned memory rather than online training; exact reuse/retention/threshold values remain owner decisions. [[components/document-reconciliation|Component card]]
