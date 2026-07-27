# PRD: сверка Table 1 и допотчёта Table 2 v1

## 1. Цель и границы

Локальный инструмент для одного пользователя сверяет исходные КС-2/КС-3/КС-6а (**Table 1**) с `Расчет доп отчета карточка 23 Хандюк.xlsx` / `Лист1` (**Table 2**), даёт человеку проверить соответствия и создаёт один самостоятельный value-only XLSX Table 2. Cloud, многопользовательский режим, изменение исходников, online training, формулы/внешние ссылки в финальном отчёте и GPT-authority — out of scope. MVP принимает XLSX и ZIP/папку с XLSX; обнаруженные XLSB фиксируются как unsupported blocker.

## 2. Проблема и доказанный контекст

В Table 2 заголовки на строках 5–6, B хранит блоки индексов, E работу, F unit, J documentary quantity, K million RUB incl. VAT, L/M current-period fields. Table 1 layouts schema-variable: 1006 CF/CG, 1004 BL/BM, 0919 CJ/CK, KITSO иной лист. Обследованный corpus содержит 347 XLSX/XLSM общим объёмом 766.15 MB. В stage 13.1 — 15 объектов, 87 строк и 15 уникальных процессов; для 12 индексов выбраны исходники, 1005/0768/0778 missing. Их semantic KS-6a sheets содержат 31,892 строк, 50–209 столбцов, 24,017 заполненных work-name cells и 1,025 уникальных нормализованных наименований. Формулы legacy не oracle и cached values могут быть stale.

## 3. Пользователь и workflow

Site presents exactly two upload zones: «Дополнительный отчёт / Table 2» for one report XLSX and «Исходные KS / Table 1» for a source folder or ZIP. CLI uses explicit report/source arguments. Пользователь явно выбирает stage и month/current period, видит hashes и semantic preflight; missing/mismatch/ambiguous stage or month blocks the run. Selector only narrows Table 1 candidates by suffix Table 2 B; workbook content proves stage. Затем система применяет versioned rules и показывает единую review table. Пользователь approve/reject/reject+comment/choose-candidate; при необходимости отдельно выбирает Remember rule. После снятия blockers он экспортирует новую копию, которая preserves validated stage/month and reopen/manifest-ом подтверждается.

## 4. Functional requirements

FR-01: Table 1/2 identities, immutable hashes and lineage follow [rules](BUSINESS_RULES.md). Table 1 calculation uses only semantic KS-6a and the proven current-cumulative whole-period-construction block; KS-2/KS-3/standalone current-month blocks are excluded. Multiple same-name blocks are not summed: exactly one may be selected by header/dependency plus 100%-leaf-row Decimal identity proof under a confirmed schema; otherwise user resolution blocks calculation.

FR-02: Unicode-aware selector сохраняет leading zero, boundary index, `6а` variants и `~$` exclusion. Candidate ranking is semantic stage → semantic month → highest explicit `редN`; mtime never decides. A remaining tie may receive a schema-quality recommendation but always requires user confirmation. If an index has no Table-1 file, the site names the missing index/object and offers three direct actions: upload that Table 1 into the current run, declare it absent and carry the immediately previous semantic month quantity/cost values, or leave the new pair blank. A supplemental upload is revalidated for index/stage/month/schema. Carry copies values only; no formula or zero substitution is allowed.

FR-03: M01–M15 are versioned. In KGS cable scope, explicit low-current/VOLS markers choose M05; otherwise M04. Wiring/device-connection, support, fastening and auxiliary rows are review-only candidates, never hard-excluded. M08 treats Table-2 «Укладка»/«Укладка трубопроводов» as aliases and auto-includes only the normalized Table-1 «Укладка трубопроводов» prefix in the same ГК object. M15 auto-includes the exact bored-drop metal-pile foundation row in ВЛ scope, hard-excludes pile tests and shows pile-head fabrication/installation unchecked as `needs_review`. Prefix, scope and exclusive ownership rules apply before fuzzy/GPT candidate suggestions.

FR-04: Semantic unit fields are compared per source row. Quantity prefers the Table-2 unit; alternatives are grouped without cross-unit addition. Unit conversion is default-off and only an explicit versioned owner-approved pair/factor may convert exact values. Monetary cost sums all approved rows. Decimal calculations retain full precision; final output uses two-decimal `ROUND_HALF_UP`.

FR-05: Site has exactly two named upload zones («Дополнительный отчёт / Table 2» one XLSX; «Исходные KS / Table 1» folder/ZIP), CLI explicit report/source args, explicit stage and month/current-period validation against semantic Table 2 headers, then one review table. Every Table-1 candidate has a direct **«Учитывать»** checkbox, source lineage, contribution, recommendation/uncertainty and optional comment; totals recalculate after each change. Unresolved blocker disables export.

FR-06: Export semantically finds/creates the selected month's quantity/cost pair and handles old→new confirmation. The only delivered artifact is one standalone editable XLSX Table 2 with values, styles, merged cells, filters, comments and colors, but zero formulas, external workbook links or connections. Table-1 formulas are never copied; existing Table-2 formulas are flattened to saved visible values in the output copy. Internal manifest/audit stays local.

FR-07: Feedback memory is versioned rules, never model training. User feedback activates exact rules after export; active rules persist indefinitely. Opposite decisions create versions, and a compact **«Запомненные правила»** list offers direct on/off and restore. History is append-only/deduplicated, excluded from GPT context and never physically deleted.

FR-08: GPT is role-bounded, strict-schema candidate-only and cannot select/sum/approve/write. Every previously unseen schema fingerprint goes through `schema_advisor`; its proposal must then be explicitly confirmed or corrected by the user and deterministically validated before entering cache. A validated cached fingerprint does not consume another call. If no model provider is configured, the same case becomes an explicit manual schema-confirmation blocker, never silent deterministic acceptance. The site may also invoke `mapping_advisor` for one unresolved process/candidate packet. A deterministic task router, not an LLM orchestrator, decides whether either worker is needed. No runtime agent exists for file selection, arithmetic, feedback activation, Excel writing or verification. Deterministic SQL resolves mappings first and suppresses mapping-AI calls; otherwise only minimal compatible projections fit the approved budgets. Model gateway must work without a paid API: allowlisted local GPT-capable CLI adapter or a manual copy/paste JSON bridge to the GPT application are valid; API adapter is optional. CLI/site keep the full explicit manual-confirmation path when no model is available.

## 5. Data and output contracts

Inputs, normalized row, decision, feedback rule and calculation contracts are defined in [architecture](ARCHITECTURE.md) and [rules](BUSINESS_RULES.md). User output = exactly one value-only Table-2 XLSX. Internal SQLite keeps hashes, schema/rule/feedback versions, decisions, exact/rendered values and per-row lineage; it is not an additional delivered report. Input hashes must remain unchanged.

## 6. Errors, recovery and privacy

Schema drift, unsupported XLSB, missing Table-2 report, multiple Table-1 candidates, missing saved value behind a formula, ambiguous match, collision, duplicate lineage, Decimal/unit mismatch and verification failure are visible blockers, never silent fallback. A missing Table-1 index source is instead a clear supplemental-upload/carry-forward/blank decision, not an error; export waits only until the user chooses or supplies a valid file. Missing cached formula value always shows file/sheet/cell and requires Excel recalculate-save-reupload; the missing-source blank branch never bypasses the global formula-flattening gate. Blank/zero substitution and automated LibreOffice recalculation are forbidden. Files and SQLite remain local; formulas/macros are never executed; GPT gets no money data.

## 7. Quality and measurable acceptance

- 100% monetary operations use Decimal; goldens: 1006 piles `261 / 37.313343`, concrete `2.36 / 0.034239`, TT `2138.059 / 33.75002661`, metal `100.39863 / 12.59387023` (quantity / million RUB).
- Reordering rows does not change result; every included/excluded value has row/file/rule lineage.
- Selector, all rule branches (including M04/M05 candidate-only until approved include sets), feedback compatibility, upload labels/count/report XLSX/source folder/ZIP, stage/month preservation, editable exports and manual/no-GPT path have automated tests; malformed GPT output is rejected deterministically.
- Metrics/tests prove average SQLite growth `≤ 1 KiB` per feedback decision after checkpoint on a 100,000-decision fixture; exact compatible active-rule lookup at 1,000,000 audit events / 100,000 active rules is p95 `≤ 100 ms` warm and `≤ 500 ms` cold on the recorded reference machine. Prompt ceilings follow BUSINESS_RULES §7; tests also prove zero duplicate raw strings, no full-history prompt and deterministic equivalence before/after retention compaction.
- Output opens editably, preserves styles/merged cells/filters/comments/colors, contains zero formulas/external links/connections and is the only delivered file; original hashes do not change and internal verification reconciles 100% changed cells and lineage.

## 8. Gate 0 and dependencies

Gate 0 product decisions are complete and recorded in BUSINESS_RULES §7, including adaptive AI context budgets and performance/storage thresholds. This remains a planning-only phase: scaffold or implementation starts only on a separate owner instruction. Feedback creation/scope/activation/retention/on-off/restore and prior rules are fixed. M02/M06 literals are fixed. CodeGraph only follows first scaffold.

## 9. Risks and non-goals

Primary risks: variable schemas, missing cached input values, mistaken unit/money semantics, accidental version selection, feedback overreach and privacy leakage. Non-goals are listed in §1; especially no formulas or external workbook dependencies in the delivered report.

## 10. Traceability matrix

| Requirement | Contract | Acceptance evidence |
| --- | --- | --- |
| Inputs/selector | BR §1–2 | Unicode, boundary, misleading filename, content-stage, missing-index supplemental-upload/carry/blank and multiple-candidate tests |
| 15 mappings | BR §3–4 | M01–M15, M04/M05 positive/cross-category/exclusion, M13/M14 and M01/M15 collision tests |
| Money/status | BR §5 | Decimal/order/golden/J-L/unit tests |
| Review/export | ARCH UX/export | one delivered XLSX, zero formulas/external links, flattened cached values, preserved styles/colors and save/reopen/internal-manifest E2E |
| GPT/manual | ARCH GPT | schema rejection + CLI adapter/manual app bridge + no-model CLI/site tests |
| Feedback memory | BR §6 | reuse/isolation/conflict/rollback/drift/duplicate, compact-storage and compaction-equivalence tests |
| AI context control | ARCH GPT | SQL-first/no-call, token ceiling and no-full-history-prompt tests |
| Delivery | ROADMAP | package exit gates and P6 audit |
