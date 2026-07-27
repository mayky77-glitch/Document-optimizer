# PRD: сверка Table 1 и допотчёта Table 2 v1

## 1. Цель и границы

Локальный инструмент для одного пользователя сверяет исходные КС-2/КС-3/КС-6а (**Table 1**) с `Расчет доп отчета карточка 23 Хандюк.xlsx` / `Лист1` (**Table 2**), даёт человеку проверить соответствия и создаёт новую редактируемую копию. Cloud, многопользовательский режим, изменение исходников, online training, автоматическая рекалькуляция Excel и GPT-authority — out of scope. MVP принимает XLSX и ZIP/папку с XLSX; обнаруженные XLSB фиксируются как unsupported blocker и переходят в отдельный adapter backlog, а не читаются частично или молча.

## 2. Проблема и доказанный контекст

В Table 2 заголовки на строках 5–6, B хранит блоки индексов, E работу, F unit, J documentary quantity, K million RUB incl. VAT, L/M current-period fields. Table 1 layouts schema-variable: 1006 CF/CG, 1004 BL/BM, 0919 CJ/CK, KITSO иной лист. В stage 13.1 наблюдались 15 индексов: 12 с кандидатами, 1005/0768/0778 missing; формулы legacy не oracle и cached values могут быть stale.

## 3. Пользователь и workflow

Site presents exactly two upload zones: «Дополнительный отчёт / Table 2» for one report XLSX and «Исходные KS / Table 1» for a source folder or ZIP. CLI uses explicit report/source arguments. Пользователь явно выбирает stage и month/current period, видит hashes и semantic preflight; missing/mismatch/ambiguous stage or month blocks the run. Selector only narrows Table 1 candidates by suffix Table 2 B; workbook content proves stage. Затем система применяет versioned rules и показывает единую review table. Пользователь approve/reject/reject+comment/choose-candidate; при необходимости отдельно выбирает Remember rule. После снятия blockers он экспортирует новую копию, которая preserves validated stage/month and reopen/manifest-ом подтверждается.

## 4. Functional requirements

FR-01: Table 1/2 identities, semantic header lookup, immutable hashes и row lineage соответствуют [rules](BUSINESS_RULES.md).

FR-02: Unicode-aware selector сохраняет leading zero, boundary index, `6а` Cyrillic/Latin/case и `~$` exclusion; semantic preflight extracts stage from workbook content and blocks missing/mismatch/ambiguity, while filename never proves stage.

FR-03: M01–M14 versioned mappings, includes/excludes/suffixes и M13/M14 collision применяются детерминированно; fuzzy/GPT только candidate. Полное отсутствие process-name candidates даёт quantity/cost `0/0` с явным статусом.

FR-04: Semantic unit fields are compared per source row (observed Table-2 F versus Table-1 J, never fixed coordinates). Quantity prefers the Table-2 unit; if unavailable, one alternative unit is summed and written as red `old/source`; multiple units produce separate subtotals and require one explicit unit-group selection without cross-unit addition. Monetary cost sums all approved rows regardless of the quantity group. Decimal pipeline sums raw RUB then divides once by `1e6`. A separate heuristic check compares `cost_mln × run_coefficient` (default `2.7`) with Table2.K: below K is an orange review warning that allows export only after acknowledgement and never changes exported cost. Automatic conversion and J/L tolerance remain Gate 0.

FR-05: Site has exactly two named upload zones («Дополнительный отчёт / Table 2» one XLSX; «Исходные KS / Table 1» folder/ZIP), CLI explicit report/source args, explicit stage and month/current-period validation against semantic Table 2 headers, then one review table. Every Table-1 candidate has a direct **«Учитывать»** checkbox, source lineage, contribution, recommendation/uncertainty and optional comment; totals recalculate after each change. Unresolved blocker disables export.

FR-06: Export makes an editable new copy preserving formulas/styles/merged/filters/comments/colors, atomically saves, reopens and reconciles manifest/original hash.

FR-07: Feedback memory is versioned and explicit, never model training; canonical SQLite entities use IDs/FKs/hashes, raw strings deduplicate once, active snapshot is separate from append-only audit, and reuse supports compatibility/undo/deactivate/rollback.

FR-08: GPT is default-off, strict-schema candidate-only and cannot select/sum/approve/write; deterministic SQL resolves first and suppresses AI call; otherwise only minimal compatible candidate/rule projections fit an owner-approved context/token budget. Model gateway must work without a paid API: local GPT-capable CLI adapter or a manual copy/paste JSON bridge to the GPT application are valid; API adapter is optional. CLI/site keep the full manual path when no model is available.

## 5. Data and output contracts

Inputs, normalized row, decision, feedback rule and calculation contracts are defined in [architecture](ARCHITECTURE.md) and [rules](BUSINESS_RULES.md). Output = new XLSX plus manifest/audit records: input/output hashes, schema/rule/feedback versions, decisions, values/statuses and per-row lineage. Input hashes must equal their import hashes after every run.

## 6. Errors, recovery and privacy

Schema drift, unsupported XLSB, missing/multiple file, ambiguous match, collision, duplicate lineage, stale formula, Decimal/unit mismatch and manifest failure are visible blockers, never silent fallback. UI/CLI shows evidence and recovery (choose candidate, fix schema, explicit skip, owner decision, re-run). Files and SQLite remain local; macros/formulas are not executed; GPT gets no money data.

## 7. Quality and measurable acceptance

- 100% monetary operations use Decimal; goldens: 1006 piles `261 / 37.313343`, concrete `2.36 / 0.034239`, TT `2138.059 / 33.75002661`, metal `100.39863 / 12.59387023` (quantity / million RUB).
- Reordering rows does not change result; every included/excluded value has row/file/rule lineage.
- Selector, all rule branches (including M04/M05 candidate-only until approved include sets), feedback compatibility, upload labels/count/report XLSX/source folder/ZIP, stage/month preservation, editable exports and manual/no-GPT path have automated tests; malformed GPT output is rejected deterministically.
- Metrics/tests prove storage growth per decision, large-corpus retrieval latency, configurable prompt-token ceiling, zero duplicate raw strings, no full-history prompt and deterministic equivalence before/after retention compaction. Numeric thresholds are owner-approved at Gate 0.
- Output opens editably and preserves formulas/styles/merged cells/filters/comments/colors; original hash does not change; manifest reconciles 100% changed cells and lineage.

## 8. Gate 0 and dependencies

No scaffold or implementation starts until owner approves every item in BUSINESS_RULES §7: M04/M05 exact include sets, M13/M14, suffix/supporting-work semantics, period semantics, quantity/new columns, J/L tolerance, automatic unit conversion, versions/stage, month/current-period semantics, freshness, display/overwrite, feedback reuse/retention/rollback and AI context/token budget plus performance/storage thresholds. Run-level coefficient, orange warning acknowledgement, unit-priority, alternative-unit grouping, cost inclusion and control formula/status are fixed. M02/M06 literals are already fixed. CodeGraph only follows first scaffold.

## 9. Risks and non-goals

Primary risks: variable schemas, stale formulas, mistaken unit/money semantics, accidental version selection, feedback overreach and privacy leakage. Non-goals are listed in §1; especially no silent rule broadening from one item to a category.

## 10. Traceability matrix

| Requirement | Contract | Acceptance evidence |
| --- | --- | --- |
| Inputs/selector | BR §1–2 | Unicode, boundary, misleading filename, content-stage and missing/multiple tests |
| 14 mappings | BR §3–4 | M01–M14, M04/M05 positive/cross-category/exclusion and M13/M14 collision tests |
| Money/status | BR §5 | Decimal/order/golden/J-L/unit tests |
| Review/export | ARCH UX/export | exact two upload zones, XLSX/folder/ZIP, stage/month preservation, preselected checkbox/comment/recalculation and save/reopen/manifest E2E |
| GPT/manual | ARCH GPT | schema rejection + CLI adapter/manual app bridge + no-model CLI/site tests |
| Feedback memory | BR §6 | reuse/isolation/conflict/rollback/drift/duplicate, compact-storage and compaction-equivalence tests |
| AI context control | ARCH GPT | SQL-first/no-call, token ceiling and no-full-history-prompt tests |
| Delivery | ROADMAP | package exit gates and P6 audit |
