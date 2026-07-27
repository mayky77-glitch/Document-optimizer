---
type: component
tags: [knowledge/component, domain/document-reconciliation, status/accepted, risk/high]
last_verified: 2026-07-28
source_paths: ["docs/PRD.md", "docs/BUSINESS_RULES.md", "docs/ARCHITECTURE.md", "docs/ROADMAP.md"]
---
# Document reconciliation

Four linked planning documents define product, domain contract, architecture and critical roadmap.

## Canonical facts

- Table 1 is source KS-2/KS-3/KS-6a; Table 2 is `Расчет доп отчета карточка 23 Хандюк.xlsx`, `Лист1`.
- Table 2 `Лист1` is 180×17; 1006 block rows 139–144. Table 1 period fields are semantic: observed 1006 CF/CG, 1004 BL/BM, 0919 CJ/CK; KITSO differs.
- Calculation reads only normalized KS-6a sheet variants and the semantic whole-period-construction block; KS-2/KS-3/month blocks are excluded and zero/multiple matches require user resolution.
- Actual corpus: 347 XLSX/XLSM, 766.15 MB. Stage 13.1 has 15 objects / 87 rows / 15 unique processes; 12 selected source KS-6a sheets total 31,892 rows, 50–209 columns, 24,017 populated name cells and 1,025 unique normalized names. Missing indices: 1005/0768/0778.
- Selection uses suffix-after-last-dot, Unicode token boundaries and `6а` Cyrillic/Latin/case; semantic workbook content, not filename, proves stage. Missing index source is named with its object and offers direct supplemental-upload/carry-previous-period/leave-blank actions; multiple files still require review.
- Multiple candidates rank by semantic stage, semantic month and highest explicit `редN`; mtime never decides. Remaining schema/data-quality tie is only a recommendation and requires user confirmation.
- [BUSINESS_RULES](../../docs/BUSINESS_RULES.md) v1 is the canonical contract for M01–M15, Decimal raw-RUB aggregation, red/yellow statuses, feedback memory and Gate 0.
- Unit columns are semantic and movable: observed Table-2 F is compared per source row with observed Table-1 J. Quantity prefers that unit; one alternative unit is summed with red `old/source`; multiple units remain separate subtotals until the user selects one. Cost always sums all approved rows.
- Unit conversion is default-off and not expected; only an explicit owner-approved versioned pair/factor may convert, with exact/raw/converted lineage and rollback. No inferred factors.
- VOLS source rows default exclusively to M14; manual M13 reassignment atomically removes M14 ownership. One source row can never contribute to both processes.
- M15 maps ВЛ pile-base work to exact bored-drop metal piles; pile tests are excluded and pile-head fabrication/installation is visible unchecked review-only. Approved pile heads affect cost, stay outside `шт` quantity and create red `шт/т`; M01/M15 cannot share a source row.
- M03/M07/M08/M12 `+ value` matches the exact normalized base or any string beginning with it plus continuation; no separate Table-2 suffix comparison, hard excludes first.
- In KGS cable scope, explicit low-current/VOLS markers choose M05; otherwise M04. Wiring/device-connection, supports, fastening and auxiliary rows are visible review-only candidates, not hard excludes.
- Feedback memory stores only user-changed/confirmed uncertain decisions. A default-on direct switch activates an exact scoped rule after successful export; off/cancelled stays audit-only, and context drift returns to review.
- Active rules persist indefinitely; opposite decisions version, and compact on/off/restore never physically deletes audit. History is deduplicated and excluded from GPT context.
- No process-name candidate produces quantity/cost `0/0`. Every candidate is visible with a preselected **«Учитывать»** checkbox, contribution, uncertainty and optional comment; user changes recalculate totals.
- Missing Table-1 file and no process match are distinct: missing index source asks for a supplemental file first, with object-level carry/blank fallbacks; `0/0` applies only when a valid source file exists but contains no process-name candidate.
- Coefficient is one editable run-level field, default `2.7`. `cost_mln × coefficient < Table2.K` produces an orange warning with inputs/result/difference; acknowledged warnings do not block export and never alter exported cost. Coefficient and acknowledgement enter manifest/audit.
- Table-2 J/L compare after `ROUND_HALF_UP` to two decimals; exact equality, `0 = 0` and blank/blank are yellow. Blank/number is not yellow and blank is not zero.
- Aggregation/control retain full Decimal precision; final quantity/cost and J/L comparison values use two-decimal `ROUND_HALF_UP`. Manifest retains exact and rendered values.
- Selected month resolves to one semantic quantity/cost pair. Missing pair is styled/appended at the right; existing pair is reused without duplication; nonblank old→new requires explicit overwrite confirmation.
- Final delivery is exactly one standalone Table-2 XLSX: Table 1 supplies saved values only, all Table-2 formulas are flattened to saved visible values, new results are numeric, and reopen verifies zero formulas/external links while preserving styles/colors/editability. Internal manifest remains local.
- Missing saved value behind a required formula blocks with file/sheet/cell evidence; recovery is Excel recalculate-save-reupload. No blank/zero substitution, formula/macro execution or LibreOffice recalc.

## Gate 0 / risks

- Gate 0 product decisions are complete; work remains planning-only until a separate implementation instruction.
- GPT packets are bounded separately: schema `8,000/1,200` for up to 6 fingerprints; mapping `4,000/600` for one process/up to 20 unique candidates; run soft budget `25,000/5,000`, then manual fallback or explicit continuation. Tokenizer/UTF-8 byte-bound packing splits without truncation; prompt cache prevents identical repeat calls.
- Runtime site AI is limited to stateless `schema_advisor` and `mapping_advisor`, invoked by a deterministic router. Every unseen schema fingerprint requires the first worker or manual schema entry when no provider exists; every proposal needs explicit user confirm/correct and deterministic validation before cache. Workers never select files, calculate, activate memory, export or verify; invalid/timeout results go to manual review without auto-retry.
- Feedback storage acceptance is `≤ 1 KiB/decision` average at 100,000 decisions; lookup p95 `≤ 100 ms` warm / `≤ 500 ms` cold at 1,000,000 events and 100,000 active rules on a recorded reference machine.
- Feedback is versioned scoped memory, never online training: canonical SQLite IDs/FKs/hashes, deduplicated raw strings, active snapshot separate from immutable audit; deterministic SQL precedes any bounded GPT projection.
- Model gateway supports disabled, local CLI and manual strict-JSON GPT-application modes without requiring an API. MVP imports XLSX/folder/ZIP; XLSB is an explicit post-MVP adapter. Implementation orchestration has a pre-P1 xhigh-profile setup/restart gate.

## Links
- [PRD](../../docs/PRD.md) · [Rules](../../docs/BUSINESS_RULES.md) · [Architecture](../../docs/ARCHITECTURE.md) · [Roadmap](../../docs/ROADMAP.md) · [[../DECISIONS|Decisions]] · [[../tasks/remediate-plan-documents|Remediation task]]
