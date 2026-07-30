# Накопительный обзор реализации

## Блок 7 — подготовка данных для обучения

- **Архивный base commit:** `1ac240d4cc766b7a4504c3ef47b8f7aed104b4ae`
- **Фактический base:** `e1c774db44baf18a68ad22fa107f86640baf4aeb`
- **Предыдущий блок:** блок 6, `CanonicalSourceRow`, DuckDB/JSONL
- **Новый публичный пакет:** `report_processor.training_data`
- **Новая команда:** `report-processor prepare-training-data`
- **Версия схемы результата:** `7.0`

### Назначение

Блок принимает канонические строки блока 6 и формирует трассируемую таблицу для
узких задач классификации, сопоставления и контроля качества. Excel повторно не
открывается; сохранённые блоком 6 значения и provenance остаются источником
истины.

### Реализовано

- прямое чтение основного DuckDB без лимита пользовательского query API;
- строгий совместимый JSONL loader без неявного приведения типов;
- нормализация Unicode, пробелов, регистра, знака `№`, кодов и единиц;
- разделение детальных, итоговых и неактуальных строк;
- маркировка `FORMULA_WITHOUT_CACHE`, `EXCEL_ERROR`, `VALUE_READ_FAILED`;
- стабильный `line_id` с length framing и SHA-256;
- удаление точных семантических дублей;
- сохранение конфликтующих строк с детерминированным ID и предупреждением;
- атомарный JSONL + metadata через writer блока 6;
- одна CLI-подкоманда с управляемыми ошибками.

### Границы

Блок не сопоставляет КС-2 ↔ КС-6а ↔ СВВР, не пересчитывает значения, не строит
train/test split и не обучает модель. Расширенная бизнес-нормализация остаётся
отдельным следующим блоком.

### Проверки

- `uv run ruff check .` — PASS;
- `uv run pytest -q` — **405 passed, 1 skipped**;
- focused Block6/7, storage, contract и CLI — **60 passed**;
- `uv lock --check`, `compileall`, `git diff --check` — PASS;
- пять новых real-data сценариев — 1517 выходных строк, уникальные `line_id`,
  согласованные metadata и неизменные SHA Excel/DuckDB;
- повторный независимый P6-аудит — PASS.

### Исправления по P6

- не-конечные и malformed Decimal отклоняются на общей границе storage;
- дедупликация учитывает все сигнатуры одной collision-группы;
- `total_cost` сохраняется в `TrainingDataRow` и участвует в сигнатуре;
- CLI защищает input от совпадения с JSONL и metadata, включая symlink;
- DuckDB-вход блока 7 открывается read-only без создания схемы или миграций;
- DuckDB schema/validation вынесены из store в отдельный модуль.

CI ветки фиксируется после публикации коммита.

## Блок 8 — бизнес-нормализация

Frozen contract: `NormalizedSourceRow`, `NormalizedBusinessKey`,
`NormalizationConfig`, `NormalizationResult`; вход `TrainingDataRow` `7.0`,
выход JSONL `8.0`, CLI `normalize-rows`. Provenance и `Decimal` сохраняются,
business `line_id` независим от physical source; exact typo dictionaries —
data-only. Collision evidence сохраняется в `NormalizationResult`; CLI строго
разделяет input, output и metadata paths.

Локальные gates: Ruff PASS; focused **8 passed**; полный suite **413 passed,
1 skipped**; отдельный 50k-row performance test **1 passed**; `compileall` и
`git diff --check` PASS. GitHub CI остаётся release gate перед merge в `main`.

Real-data gate на исходной комбинированной книге 0784 и reviewed-схеме
листа КС-2: **780** канонических строк → **378** `TrainingDataRow` →
**378** `NormalizedSourceRow`. Все числа остались `Decimal`, provenance
полон, повторная нормализация детерминирована. **26** совпадений
business key отражены в collision statistics/warnings; строки не
отфильтрованы. SHA-256 и размер исходного Excel до/после совпали.
Автоанализ трёх реальных книг также подтвердил безопасный
`LOW_CONFIDENCE_SCHEMA` вместо необоснованного угадывания колонок.

## Блоки 9–10

Блок 9 публикует read-only контракт `TargetReportSchema-9.0`: snapshots
структуры/формул/кэша, provenance, диагностику и описательные write plans.
На реальном XLSX получены 107 строк, 60 планов и 0 diagnostics; исходник
не изменён.

Блок 10 публикует data-only контракт `RuleConfigurationVersion-1.0` для
JSON/YAML. Валидация использует `Decimal`, canonical JSON и content hash;
дубликаты YAML, tags, anchors/aliases и исполняемые конструкции запрещены.
M01–M15 представлены структурированными issues/conflicts.

Проверки: focused **28 passed**, полный suite **441 passed, 1 skipped**,
Ruff PASS. До отдельного PR/CI gate блоки не считаются опубликованными в
`main`.

## Блок 11 — аналитический DuckDB

Реализован `AnalyticalStore-11.0` на схеме `AnalyticalSchema-1` в отдельном
пакете `report_processor.analytics`. API принимает нормализованные строки,
целевые строки с явным fingerprint/source context и проверенный набор правил.
Схема инициализируется транзакционно и не затрагивает storage v1.

Проверены provenance, строгие Decimal-типы, идемпотентная загрузка,
deduplication, конфликт payload с rollback, parameterized SQL для bounded named
queries, фиксированный allowlist фильтров и атомарный diagnostics JSONL export.
Focused Block 11 с regression storage v1: **47 passed**. Real-data gate на
reviewed КС-2 и целевом отчёте загрузил **382** нормализованные source rows,
**107** target rows и **34** rule clauses; повторная загрузка полностью
идемпотентна. Diagnostics export содержит **246** строк и воспроизводимый
SHA-256; исходные XLSX не изменились. Полный локальный suite после интеграции:
**464 passed**. Блок принят в `main` через PR #11 после успешного GitHub
Actions. Matching/business logic не смешана с аналитическим хранилищем.

## Блок 14 — quality-control write gate

Контракт: `QualityControlContract-14.0` / `QualityControlEngine-14.0`.
API: `evaluate_quality_control(match_results, calculation_results, rule_set) -> QualityControlReport`.
Решения и находки типизированы через `WriteDecision`, `QualityIssueSeverity` и
`QualityIssueCode`.
`ValidatedRuleSet.defaults.cost_tolerance_ratio` — единственный источник
tolerance. Проверяются identity/cardinality, required values, writable targets,
formula cache/Excel errors, provenance, trace/totals/formula consistency,
normalized units и Decimal tolerance; precedence решений —
`BLOCK_WRITE > REQUIRE_MANUAL_REVIEW > ALLOW_WRITE_WITH_WARNINGS > ALLOW_WRITE`.
Raw cells, formulas и document content не попадают в отчёт; workbook read-only.

Evidence: synthetic set — 7 PASS; real-data — `REQUIRE_MANUAL_REVIEW`, 0 blocking,
digest `c20ecd6839a44cfb90586858f9a7699180f28fde2f299819624c2d3606689492`, входы
не изменились. Полный integration suite: **490 passed**; Ruff, format, clean
install, compileall и `git diff --check` — PASS. READY/main требует зелёного PR.

## Блок 15.1 — numeric-only formula materialization

`ExcelWriterContract-15.1` допускает запись только для двух allow decisions;
manual review/block возвращают `SKIPPED_DECISION`. Записываются только
`CURRENT_PERIOD_QUANTITY` и `CURRENT_PERIOD_COST` из конечных `Decimal`, без
float, пересчёта, округления, quantize или очистки через `None`.

Реализация использует targeted OOXML update без `openpyxl.save`. Output содержит
только numeric literals: исходные worksheet formulas остаются в immutable source
и internal provenance, но не попадают в пользовательский отчёт. При наличии
формул LibreOffice headless пересчитывает private temp copy с isolated profile;
при нуле формул запуск пропускается. Unavailable, timeout, error, blank, text и
non-finite result блокируют publication. Source identity, atomic temp verification
и hard-link no-clobber сохраняются; CLI нет.

Локальный evidence Block 15.1: real-data suite — **7 passed in 44.38s**;
полный suite с real XLSX и slow performance — **514 passed in 80.22s**.
Ruff, format, clean sync, compileall и `git diff --check` — PASS. Реальный
output содержит `D30 = 0`, формулы **14 → 0**, merged ranges — **128**;
SHA-256, size и `mtime` обеих исходных книг не изменились. READY/main/CI
требуют зелёного Pull Request.

## Блок 12 — детерминированный matching engine

Реализованы `MatchingContract-12.0` и `MatchingEngine-12.0` в отдельном
пакете `report_processor.matching`. Движок строит все кандидаты по семи
замороженным стратегиям, сохраняет provenance, объяснения и blockers.
Ранжирование использует только ordinal стратегии; confidence остаётся
`Decimal`-метаданными. Равенство лучших кандидатов не разрешается молча.

Проверены duplicate IDs, стабильность порядка и SHA-идентификаторов, точные и
структурные стратегии, fuzzy-only manual review, `REVIEW`, `EXCLUDE`,
игнорирование неподтверждённых правил и невозможность выбрать ambiguous
кандидата. Focused gate: **6 passed**, Ruff и format PASS.

Real-data gate на reviewed КС-2 и целевом отчёте: **382** source rows,
**107** target rows, **35** кандидатов; результаты — **1 matched**,
**5 ambiguous**, **101 unmatched**. SHA-256 канонического результата:
`ecfc6fedfc2c3797ab84c769ec9ddd32a16efb69f61964e2cf43122e283106d3`.
Обратный порядок входных строк даёт тот же результат; SHA-256, размер и
`mtime` обеих XLSX до/после совпадают. Полный suite и GitHub Actions остаются
release gates integration-ветки.

## Блок 13 — calculation engine

Frozen: `CalculationContract-13.0` / `CalculationEngine-13.0`. Только
`MATCHED` с выбранным кандидатом получает totals; ambiguous/manual review и
no-match — нет. `period_quantity`/`period_cost` — `Decimal`; coefficient,
aggregate-first и одно финальное `ROUND_HALF_UP`. Signed negative adjustments
сохраняются с trace warning. Approved `EXCLUDE` побеждает, `REVIEW` требует
ручного решения, quantity/cost независимо. Exact canonical categories
work/material/service; отсутствующий `cost_type_code` — `UNCLASSIFIED`, без
text inference. Полный formula/provenance trace, workbook не изменяется. Все
382 reviewed source rows имеют отсутствующий `cost_type_code`.

Focused calculation gate: **11 passed**, real-XLSX gate: **1 passed**,
полный suite: **482 passed**; Ruff, format, clean install, compileall и
`git diff --check` — PASS. Сквозной real-data результат: **382** source rows,
**107** target rows, **35** кандидатов; calculation-статусы
**1 calculated**, **5 manual_review**, **101 no_match**. Единственный вклад
остался `UNCLASSIFIED`. Канонический SHA-256 calculation-результата:
`6b814337cb55e574cae7ab42bf9c4d81af99bc163067d76c31d56085c4ee8d54`.
SHA-256, размер и `mtime` обеих исходных XLSX неизменны. GitHub CI и статус
`main` подтверждаются только после Pull Request.

## Блок 16 — audit implementation review

Accepted evidence commit `99d7ffedf5a2d65cccf1c21206c3fbe847d83a6a`, frozen base
`e951bef5397d21037680901cbb52752b5556d9b8`: focused+slow+real **33 passed**;
полный real+slow suite **547 passed in 89.32s**; 100k **583.3 B/event**,
append p95 **0.072 ms**; real files unchanged.
Проверены append-only chain/transitions, redacted deterministic exports,
cross-store recovery, feedback только после `EXPORT_VERIFIED`, compaction,
no-clobber и invalid-output cleanup. Block 15 принят: PR #15, CI `30569460356`,
main CI `30569606304`, 514 passed/real 7 passed. Block 16 принят: PR #16,
PR CI `30572493480`, main SHA `ca6300471b52ba1ef80585b3881cb77e04a6be50`,
post-merge main CI `30572598426` — success.

## Блок 17 — processing controller (принят в main)

Frozen API: `process_report`, `process_reports` и CLI `report-processor process --mode {inspect,dry-run,write}`. Modes: inspect без мутаций, dry-run без публикации, write с QC gate; states `PENDING`, `RUNNING`, `SUCCEEDED`, `SUCCEEDED_WITH_WARNINGS`, `MANUAL_REVIEW_REQUIRED`, `QUALITY_BLOCKED`, `FAILED`; exit codes `0`–`6`. Focused **21 passed**; полный real+slow suite **569 passed in 92.84s**. Реальный inspect-контроллер прошёл, обе XLSX неизменны. Принят через PR #17: PR CI `30575326764`, post-merge main CI `30575425467`, main SHA `322cb9ce08f14c017dbdc3bf16c5b91b33238e63`.

## Блок 18 — final implementation review

Pinned RAG: `cointegrated/rubert-tiny2` revision
`e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae`, 29.4M params, 312 dimensions,
Russian; lazy local load, normalized cosine и deterministic top-k. Unavailable
dependency/model is controlled; Block 12 remains authoritative.

Локальная панель изолирует upload в private workspace, повторно проверяет SHA
входов, redacts server paths, ограничивает размеры и выдаёт result только после
явных решений по каждой RAG-связи. Решения имеют effect
`review_journal_only`; matching молча не меняется. UI поставляется внутри wheel,
использует `#0079C2` только для панели и отдельные semantic colors.

Evidence: full real+model+slow **603 passed in 119.80s**; real admin
**1 passed in 4.49s**; desktop/mobile Chrome PASS с `0` console/page/external
errors; clean base/RAG installs, wheel assets, Ruff, format, compileall,
JS syntax и diff-check PASS. Реальные XLSX сохранили исходные SHA.
PR #18 принят: PR CI `30580440694`, post-merge main CI `30580539301` — success;
main SHA `d54fcce5a71c85a1812a3b9209a815499c216e9a`.
