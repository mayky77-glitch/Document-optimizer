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
