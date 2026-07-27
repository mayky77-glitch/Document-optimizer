# PRD: сверка Table 1 и допотчёта Table 2 v1

## 1. Цель и границы

Локальный инструмент для одного пользователя сверяет исходные КС-2/КС-3/КС-6а (**Table 1**) с `Расчет доп отчета карточка 23 Хандюк.xlsx` / `Лист1` (**Table 2**), даёт человеку проверить соответствия и создаёт один самостоятельный value-only XLSX Table 2. Cloud, многопользовательский режим, изменение исходников, online training, формулы/внешние ссылки в финальном отчёте и GPT-authority — out of scope. MVP принимает XLSX и ZIP/папку с XLSX; обнаруженные XLSB фиксируются как unsupported blocker.

## 2. Проблема и доказанный контекст

В Table 2 заголовки на строках 5–6, B хранит блоки индексов, E работу, F unit, J documentary quantity, K million RUB incl. VAT, L/M current-period fields. Table 1 layouts schema-variable: 1006 CF/CG, 1004 BL/BM, 0919 CJ/CK, KITSO иной лист. В stage 13.1 наблюдались 15 индексов: 12 с кандидатами, 1005/0768/0778 missing; формулы legacy не oracle и cached values могут быть stale.

## 3. Пользователь и workflow

Site presents exactly two upload zones: «Дополнительный отчёт / Table 2» for one report XLSX and «Исходные KS / Table 1» for a source folder or ZIP. CLI uses explicit report/source arguments. Пользователь явно выбирает stage и month/current period, видит hashes и semantic preflight; missing/mismatch/ambiguous stage or month blocks the run. Selector only narrows Table 1 candidates by suffix Table 2 B; workbook content proves stage. Затем система применяет versioned rules и показывает единую review table. Пользователь approve/reject/reject+comment/choose-candidate; при необходимости отдельно выбирает Remember rule. После снятия blockers он экспортирует новую копию, которая preserves validated stage/month and reopen/manifest-ом подтверждается.

## 4. Functional requirements

FR-01: Table 1/2 identities, immutable hashes and lineage follow [rules](BUSINESS_RULES.md). Table 1 calculation uses only semantic KS-6a and the whole-period-construction block; KS-2/KS-3/current-month blocks are excluded, and zero/multiple matches block until resolved.

FR-02: Unicode-aware selector сохраняет leading zero, boundary index, `6а` variants и `~$` exclusion. Candidate ranking is semantic stage → semantic month → highest explicit `редN`; mtime never decides. A remaining tie may receive a schema-quality recommendation but always requires user confirmation.

FR-03: M01–M14 are versioned. M03/M07/M08/M12 `+ value` uses exact-or-normalized-prefix semantics with any continuation and hard-exclude priority. VOLS rows default exclusively to M14 with atomic M13 reassignment. Fuzzy/GPT only propose candidates. No process-name candidate gives `0/0`.

FR-04: Semantic unit fields are compared per source row. Quantity prefers the Table-2 unit; alternatives are grouped without cross-unit addition. Unit conversion is default-off and only an explicit versioned owner-approved pair/factor may convert exact values. Monetary cost sums all approved rows. Decimal calculations retain full precision; final output uses two-decimal `ROUND_HALF_UP`.

FR-05: Site has exactly two named upload zones («Дополнительный отчёт / Table 2» one XLSX; «Исходные KS / Table 1» folder/ZIP), CLI explicit report/source args, explicit stage and month/current-period validation against semantic Table 2 headers, then one review table. Every Table-1 candidate has a direct **«Учитывать»** checkbox, source lineage, contribution, recommendation/uncertainty and optional comment; totals recalculate after each change. Unresolved blocker disables export.

FR-06: Export semantically finds/creates the selected month's quantity/cost pair and handles old→new confirmation. The only delivered artifact is one standalone editable XLSX Table 2 with values, styles, merged cells, filters, comments and colors, but zero formulas, external workbook links or connections. Table-1 formulas are never copied; existing Table-2 formulas are flattened to saved visible values in the output copy. Internal manifest/audit stays local.

FR-07: Feedback memory is versioned and explicit, never model training; canonical SQLite entities use IDs/FKs/hashes, raw strings deduplicate once, active snapshot is separate from append-only audit, and reuse supports compatibility/undo/deactivate/rollback.

FR-08: GPT is default-off, strict-schema candidate-only and cannot select/sum/approve/write; deterministic SQL resolves first and suppresses AI call; otherwise only minimal compatible candidate/rule projections fit an owner-approved context/token budget. Model gateway must work without a paid API: local GPT-capable CLI adapter or a manual copy/paste JSON bridge to the GPT application are valid; API adapter is optional. CLI/site keep the full manual path when no model is available.

## 5. Data and output contracts

Inputs, normalized row, decision, feedback rule and calculation contracts are defined in [architecture](ARCHITECTURE.md) and [rules](BUSINESS_RULES.md). User output = exactly one value-only Table-2 XLSX. Internal SQLite keeps hashes, schema/rule/feedback versions, decisions, exact/rendered values and per-row lineage; it is not an additional delivered report. Input hashes must remain unchanged.

## 6. Errors, recovery and privacy

Schema drift, unsupported XLSB, missing/multiple file, missing saved value behind a formula, ambiguous match, collision, duplicate lineage, Decimal/unit mismatch and verification failure are visible blockers, never silent fallback. Missing cached value shows file/sheet/cell and requires Excel recalculate-save-reupload; blank/zero substitution and automated LibreOffice recalculation are forbidden. Files and SQLite remain local; formulas/macros are never executed; GPT gets no money data.

## 7. Quality and measurable acceptance

- 100% monetary operations use Decimal; goldens: 1006 piles `261 / 37.313343`, concrete `2.36 / 0.034239`, TT `2138.059 / 33.75002661`, metal `100.39863 / 12.59387023` (quantity / million RUB).
- Reordering rows does not change result; every included/excluded value has row/file/rule lineage.
- Selector, all rule branches (including M04/M05 candidate-only until approved include sets), feedback compatibility, upload labels/count/report XLSX/source folder/ZIP, stage/month preservation, editable exports and manual/no-GPT path have automated tests; malformed GPT output is rejected deterministically.
- Metrics/tests prove storage growth per decision, large-corpus retrieval latency, configurable prompt-token ceiling, zero duplicate raw strings, no full-history prompt and deterministic equivalence before/after retention compaction. Numeric thresholds are owner-approved at Gate 0.
- Output opens editably, preserves styles/merged cells/filters/comments/colors, contains zero formulas/external links/connections and is the only delivered file; original hashes do not change and internal verification reconciles 100% changed cells and lineage.

## 8. Gate 0 and dependencies

No scaffold or implementation starts until owner approves every item in BUSINESS_RULES §7: M04/M05 include/supporting-work policy, feedback reuse/retention/rollback and AI context/token budget plus performance/storage thresholds. Prefix suffix semantics, M14/M13 ownership and prior rules are fixed. M02/M06 literals are fixed. CodeGraph only follows first scaffold.

## 9. Risks and non-goals

Primary risks: variable schemas, missing cached input values, mistaken unit/money semantics, accidental version selection, feedback overreach and privacy leakage. Non-goals are listed in §1; especially no formulas or external workbook dependencies in the delivered report.

## 10. Traceability matrix

| Requirement | Contract | Acceptance evidence |
| --- | --- | --- |
| Inputs/selector | BR §1–2 | Unicode, boundary, misleading filename, content-stage and missing/multiple tests |
| 14 mappings | BR §3–4 | M01–M14, M04/M05 positive/cross-category/exclusion and M13/M14 collision tests |
| Money/status | BR §5 | Decimal/order/golden/J-L/unit tests |
| Review/export | ARCH UX/export | one delivered XLSX, zero formulas/external links, flattened cached values, preserved styles/colors and save/reopen/internal-manifest E2E |
| GPT/manual | ARCH GPT | schema rejection + CLI adapter/manual app bridge + no-model CLI/site tests |
| Feedback memory | BR §6 | reuse/isolation/conflict/rollback/drift/duplicate, compact-storage and compaction-equivalence tests |
| AI context control | ARCH GPT | SQL-first/no-call, token ceiling and no-full-history-prompt tests |
| Delivery | ROADMAP | package exit gates and P6 audit |
