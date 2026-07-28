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
- Calculation reads only normalized KS-6a and the proven current-cumulative whole-period block. Multiple same-name blocks require header/dependency plus 100%-leaf Decimal identity under a confirmed schema; no rightmost heuristic or independent summing. Zero/multiple proof results require user resolution.
- Actual analyzed corpus: 347 XLSX, 766.15 MB. Stage 13.1 has 15 objects / 87 rows / 15 unique processes; 12 selected source KS-6a sheets total 31,892 rows, 50–209 columns, 24,017 populated name cells and 1,025 unique normalized names. Missing indices: 1005/0768/0778.
- Selection uses suffix-after-last-dot, Unicode token boundaries and `6а` Cyrillic/Latin/case; semantic workbook content, not filename, proves stage. Missing index source is named with its object and offers direct supplemental-upload/carry-previous-period/leave-blank actions; multiple files still require review.
- Multiple candidates rank by semantic stage, semantic month and highest explicit `редN`; mtime never decides. Remaining schema/data-quality tie is only a recommendation and requires user confirmation.
- [BUSINESS_RULES](../../docs/BUSINESS_RULES.md) v1 is the canonical contract for M01–M15, Decimal raw-RUB aggregation, red/yellow statuses, feedback memory and Gate 0.
- Unit columns are semantic and movable: observed Table-2 F is compared per source row with observed Table-1 J. Quantity prefers that unit; one alternative unit is summed with red `old/source`; multiple units remain separate subtotals until the user selects one. Cost always sums all approved rows.
- Unit conversion is default-off and not expected; only an explicit owner-approved versioned pair/factor may convert, with exact/raw/converted lineage and rollback. No inferred factors.
- M12 auto-includes the anchor-end-support prefix and exact reinforced-concrete-support rows only in `шт`: 4 observed auto rows. Three same-name `т` rows are excluded; 16 other anchor/intermediate support sets are unchecked review.
- Exact VOLS source rows default exclusively to M14 (3 observed `м` rows); 18 explicit-KLS-section leaves are unchecked M14 review. M13 has no baseline auto-match and exposes 16 power-cable/conductor/crossing/joint rows unchecked. Manual M13 reassignment atomically removes M14 ownership. One source row can never contribute to both processes.
- M01 in KGS/GK auto-includes only exact bored-drop metal-pile foundations: 45 observed `шт` rows. Thirty-nine test rows are excluded; 44 pile-head `т` and 37 pile/head coating `м2` rows stay outside. Six populated examples prove exact-base-only results; 0621 changes from `107` to `188 шт / 23.92` million RUB.
- M15 maps ВЛ pile-base work to exact bored-drop metal piles; pile tests are excluded and pile-head fabrication/installation is visible unchecked review-only. Approved pile heads affect cost, stay outside `шт` quantity and create red `шт/т`; M01/M15 cannot share a source row.
- Concrete target dispatch is scope-exclusive: КГС→M02 four-name exact list (7 observed `м3` rows), ГК→M09 two-foundation-name exact list (6 observed `м3` rows), ВЛ→no baseline auto-rule. Concrete preparation is unchecked review and reinforced concrete is excluded. Available ВЛ without an allowed name yields `0/0`; missing 0768/0778 and 1005 still use missing-source handling. Future non-reinforced ВЛ approval can activate only an exact scoped feedback rule after export.
- M03/M07/M08/M12 `+ value` matches the exact normalized base or any string beginning with it plus continuation; no separate Table-2 suffix comparison, hard excludes first. M03 auto-includes only «Монтаж ТТ» exact/prefix: six observed 1004/1006/0621 rows use `м`, producing red target `ст/м`; broader pipeline/insert installation is unchecked review-only, while headings/tests/purging/insulation stay out. M07 auto-includes only «Сварка на трассе трубопроводов» exact/prefix: 47 observed 0919/0918/0685/0686 rows use `км`; other future welding is unchecked review. M08 aliases Table-2 «Укладка»/«Укладка трубопроводов» but only a Table-1 pipe-laying prefix in the same ГК object auto-matches; 18 observed rows use `км`, while container/geomaterial laying stays out. M10/M11 exact-match only pipe-trench backfill/development literals: 22 observed `км` rows each; 62 generic soil-backfill and 125 other development rows in `м3` stay outside.
- In KGS, a normalized direct cable/wire-laying action is required: explicit low-current/VOLS marker chooses M05, otherwise M04. Observed M04 has 10 `м` rows; M05 has 9 `м` plus one `шт`, requiring the recommended `м` quantity group and red `км/м`; the checked `шт` row affects cost only unless disabled. Seventeen wiring and 13 tray/rack/support rows are unchecked review; 13 grounding rows are excluded; 3 cable-shelter metalwork rows stay exclusively M06. Missing 1005 uses missing-source handling.
- M06 in KGS/GK auto-includes four approved normalized metalwork families with continuations: 59 observed `т` rows. Twenty mast/tank rows are excluded by name regardless of unit. Six generic m/k, 8 platform/bridge/railing, 3 non-approved-small and 4 GK cable-stand rows are unchecked M06 review; 3 KGS cable stands stay only in M04/M05. Thirty-three AKZ/fireproof-coating rows are outside.
- Feedback memory stores only user-changed/confirmed uncertain decisions. A default-on direct switch activates an exact scoped rule after successful export; off/cancelled stays audit-only, and context drift returns to review.
- Active rules persist indefinitely; opposite decisions version, and compact on/off/restore never physically deletes audit. History is deduplicated and excluded from GPT context.
- No process-name candidate produces quantity/cost `0/0`. Every candidate is visible with a preselected **«Учитывать»** checkbox, contribution, uncertainty and optional comment; user changes recalculate totals.
- Missing Table-1 file and no process match are distinct: missing index source asks for a supplemental file first, with object-level carry/blank fallbacks; `0/0` applies only when a valid source file exists but contains no process-name candidate.
- Coefficient is one editable run-level field, default `2.7`. A shortfall outside the tolerated branch below produces an orange warning with inputs/result/difference; acknowledged warnings do not block export and never alter exported cost. Coefficient and acknowledgement enter manifest/audit.
- Exception: if numeric J and calculated L match after two-decimal rounding, a shortfall no greater than 5% of K is normal `cost_check_tolerated`, not orange and not acknowledgement-gated. Exact difference and versioned tolerance remain auditable.
- Table-2 J/L compare after `ROUND_HALF_UP` to two decimals; exact equality, `0 = 0` and blank/blank are yellow. Blank/number is not yellow and blank is not zero.
- Aggregation/control retain full Decimal precision; final quantity/cost and J/L comparison values use two-decimal `ROUND_HALF_UP`. Manifest retains exact and rendered values.
- Selected month resolves to one semantic quantity/cost pair. Missing pair is styled/appended at the right; existing pair is reused without duplication; nonblank old→new requires explicit overwrite confirmation.
- Final delivery is exactly one standalone Table-2 XLSX: Table 1 supplies saved values only, all Table-2 formulas are flattened to saved visible values, new results are numeric, and reopen verifies zero formulas/external links while preserving styles/colors/editability. Internal manifest remains local.
- Missing saved value behind a required formula blocks with file/sheet/cell evidence; recovery is Excel recalculate-save-reupload. No blank/zero substitution, formula/macro execution or LibreOffice recalc.
- A single alternative source unit is a red review warning and may export as `old/source`; only an unresolved choice among multiple unit groups blocks export. ZIP imports use isolated extraction, reject traversal/absolute/symlink entries and enforce recorded resource limits above the reference corpus.
- Uncertain candidates remain `pending` until direct include/exclude even when a recommended action is highlighted. Target-month pair and previous-pair cardinalities are separate; carry is disabled with evidence unless the prior pair is unique.
- Numeric cells cross the adapter as raw-lexeme Decimal canonicalized to 15 significant digits, never binary float. The local site is loopback-only with unguessable per-run session plus Host/Origin/CSRF and cross-session protection.

## Gate 0 / risks

- Gate 0 product decisions are complete; work remains planning-only until a separate implementation instruction.
- GPT packets are bounded separately: schema `8,000/1,200` for up to 6 fingerprints; mapping `4,000/600` for one process/up to 20 unique candidates; run soft budget `25,000/5,000`, then manual fallback or explicit continuation. Tokenizer/UTF-8 byte-bound packing splits without truncation; prompt cache prevents identical repeat calls.
- Runtime site AI is limited to stateless `schema_advisor` and `mapping_advisor`, invoked by a deterministic router. Every unseen schema fingerprint requires the first worker or manual schema entry when no provider exists; every proposal needs explicit user confirm/correct and deterministic validation before cache. Workers never select files, calculate, activate memory, export or verify; invalid/timeout results go to manual review without auto-retry.
- Feedback storage acceptance is `≤ 1 KiB/decision` average at 100,000 decisions; lookup p95 `≤ 100 ms` warm / `≤ 500 ms` cold at 1,000,000 events and 100,000 active rules on a recorded reference machine.
- Feedback is versioned scoped memory, never online training: canonical SQLite IDs/FKs/hashes, deduplicated raw strings, active snapshot separate from immutable audit; deterministic SQL precedes any bounded GPT projection.
- Model gateway supports disabled, local CLI and manual strict-JSON GPT-application modes without requiring an API. MVP imports XLSX/folder/ZIP; XLSB is an explicit post-MVP adapter. Implementation orchestration has a pre-P1 xhigh-profile setup/restart gate.

## Links
- [PRD](../../docs/PRD.md) · [Rules](../../docs/BUSINESS_RULES.md) · [Architecture](../../docs/ARCHITECTURE.md) · [Roadmap](../../docs/ROADMAP.md) · [[../DECISIONS|Decisions]] · [[../tasks/remediate-plan-documents|Remediation task]]
