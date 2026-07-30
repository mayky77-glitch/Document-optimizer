# Архитектура проекта

## Реализованная цепочка

```text
каталог / файл / ZIP
        ↓
классификация имени
        ↓
сканер файловой системы или каталога ZIP
        ↓
FileManifestEntry[]
        ↓
ManifestSummary + FileManifest
        ↓
атомарный JSON
```

Блок 2 принимает готовый `FileManifest`, обогащает его копию индексами и
перестраивает только сводку. Он не сканирует источник повторно и не открывает
документы.

Блок 3 обогащает этот же манифест периодом, редакцией и статусами имени, а
затем выбирает источник только по явному запросу. При бизнесовой ничьей
автоматический выбор запрещён.

Блок 4 принимает выбранный `SourceCandidate`. Обычный файл проверяется без
копирования; ZIP-запись извлекается только в `TemporaryWorkspace` после
проверки пути, лимита размера и CRC. Затем `openpyxl` открывает одну книгу в
двух read-only представлениях (`data_only=False` и `data_only=True`), которые
живут и закрываются вместе. Следующий блок должен использовать
`prepared_workbook_session`, а не открывать путь напрямую.

Блок 5 принимает эту сессию и только описывает структуру: bounded scan →
классификация листа → заголовок → логические столбцы → `WorkbookSchema`.
Модули `schema/` разделяют scan, merged cells, классификацию, заголовки,
столбцы, confidence, validation и JSON; данные строк не извлекаются.

Блок 6 использует цепочку `inventory → selection → materialization/session →
schema → adapters/extraction → serialization/CLI`. Готовая схема блока 5
управляет извлечением; новые Excel-фикстуры для этого блока не добавляются.
Адаптеры КС-2, КС-6а и СВВР строят канонические строки с raw/cached/formula
значениями и provenance источника/ячейки. Неразрешённые и не-OK столбцы
пропускаются, malformed schema обрабатывается контролируемо; формулы не
вычисляются, а `ArrayFormula` нормализуется.

`extract-rows` принимает manifest или selection, schema и output, поддерживает
sheet/type, limits и форматы DuckDB/JSONL/JSON. DuckDB — основной выход по
умолчанию: `DuckDBStore.write_rows()` сохраняет поток в одной транзакции через
idempotent upsert по `row_id`. JSONL с `*.meta.json` и JSON остаются явными
форматами экспорта/аудита и записываются атомарно. Схема DuckDB v1 поддерживает
только создание и проверку текущей версии: старые миграции не реализованы, более
новая версия отклоняется. `DuckDBStore` владеет соединением и должен закрываться
контекстным менеджером или `close()`; `StorageQuery` даёт ограниченные equality-
фильтры source file, индекса, периода и типа. Неопределённая схема или
отсутствие поддерживаемого листа дают контролируемый нулевой результат либо
отказ на ручную проверку, без угадывания. Жизненный цикл чтения остаётся
read-only для `.xlsx`/`.xlsm` и выбранной ZIP-записи.

Контракт таблиц и schema validation находятся в `storage/schema.py`; операции
чтения/записи — в `storage/duckdb_store.py`. Downstream-этапы открывают готовую
DuckDB с `read_only=True`: создание схемы и миграции разрешены только владельцу
storage на этапе записи блока 6.

Блок 7 является downstream-этапом `CanonicalSourceRow → TrainingDataRow`.
`prepare-training-data` читает основной DuckDB блока 6 напрямую через
`DuckDBStore.iter_all_rows()` либо принимает явный JSONL-аудит. Excel повторно
не открывается. `training_data/` разделяет классификацию, нормализацию,
качество, идентификаторы, ввод и оркестрацию. Результат записывается существующим
атомарным JSONL writer вместе с metadata схемы `7.0`. Модель сохраняет все
числовые поля, включая `total_cost`; не-конечные Decimal отклоняются до
классификации.

## Блок 8: бизнес-нормализация

Поток блока 8: `TrainingDataRow (7.0) → NormalizedSourceRow (8.0)`. Публичные
модели — `NormalizedSourceRow`, `NormalizedBusinessKey`, `NormalizationConfig`
и `NormalizationResult`; CLI — `normalize-rows`. Business `line_id` строится
из бизнес-ключа и не зависит от физического источника. Provenance и `Decimal`
переносятся без потери. Exact typo dictionaries задаются только данными
конфигурации. Междокументный merge, пересчёт и изменение исходников не входят
в scope.

## Структура пакета

```text
src/report_processor/
├── cli.py                         # только разбор CLI и связывание API
├── domain/
│   ├── models.py                  # типизированные dataclass-модели
│   ├── statuses.py                # StatusCode
│   └── exceptions.py              # контролируемые ошибки
└── inventory/
    ├── file_classifier.py         # классификация без открытия файла
    ├── scanner.py                 # каталог и одиночный файл
    ├── archive_scanner.py         # только центральный каталог ZIP
    ├── manifest_builder.py        # оркестрация и сводка
    ├── serialization.py           # JSON, валидация и атомарная запись
    └── file_manifest.py           # compatibility imports первой версии
├── identifiers/
│   ├── normalization.py            # Unicode-нормализация текста идентификатора
│   ├── document_index.py           # извлечение, оценка уверенности и сравнение
│   ├── manifest_enricher.py        # чистое обогащение FileManifest
│   └── models.py                   # неизменяемые модели индекса и кандидата
├── metadata/                        # период, редакция и статусы имени
└── selection/                       # фильтрация, оценка, ранжирование и JSON результата
├── materialization/                  # безопасное получение обычного файла или ZIP-записи
├── excel/                            # формат, две workbook-проекции и метаданные
├── workflow.py                       # жизненный цикл materialization → session
└── cli_inspect.py                    # команда inspect-workbook
```

## Блоки 9–10

`target_report/` читает целевой лист через готовую read-only workbook session.
Он разделяет semantic recovery, row extraction, formula-cache trust, provenance
и descriptive write plans; планы не применяются. Источник защищён fingerprint и
stat checks, неоднозначный выбор требует явного override.

`business_rules/` разделяет parsing, defaults, conflict detection и validation.
Парсер принимает только data-only JSON/YAML, строит canonical JSON и SHA-256.
Правила не исполняются; unsafe YAML-конструкции возвращаются как ошибки.

## Блок 11: аналитический слой

`analytics/` — отдельная граница хранения для downstream-аналитики. Он принимает
типизированные результаты блоков 8–10 и не изменяет рабочую схему `storage/`.
`AnalyticalStore` владеет отдельным соединением DuckDB и создаёт/проверяет только
`AnalyticalSchema-1`.

Идентификаторы и payload hash проверяются до вставки. Повторная загрузка того же
payload — no-op, конфликт — транзакционная ошибка с rollback. Значения данных
передаются параметрами DuckDB; динамическими остаются только заранее разрешённые
query templates и имена. `v_diagnostics` экспортируется во временный JSONL с
последующей атомарной заменой. Сопоставление строк и бизнес-логика блока 12 не
выполняются.

## Блок 12: matching engine

`matching/` — чистая граница сопоставления между нормализованными строками
источника и строками целевого отчёта. Она зависит от публичных контрактов
`normalization/`, `target_report/` и `business_rules/`, но не пишет в DuckDB,
Excel или файловую систему.

`engine.match_rows` сначала проверяет идентичность входов, сортирует строки по
стабильным идентификаторам и строит все применимые кандидаты. Стратегии имеют
замороженный ordinal; confidence хранится как `Decimal`, но не меняет
приоритет. Единственный лучший auto-selectable кандидат получает `MATCHED`.
Ordinal-tie, fuzzy-only и подтверждённый `REVIEW` получают `AMBIGUOUS` без
выбранного кандидата. Если все кандидаты заблокированы `EXCLUDE`, результат
остаётся `UNMATCHED`.

`MatchCandidate` сохраняет исходную строку, все сработавшие стратегии,
rule IDs, blockers, explanation и provenance обеих сторон. Идентификаторы
кандидатов и результатов являются SHA-256 от версий контрактов и входной
идентичности. Наборы кандидатов и результатов сортируются детерминированно.
Исполняемая конфигурация, произвольный SQL, расчёт сумм и workbook writes
отсутствуют.

## Блок 14: deterministic quality-control gate

Quality-control принимает `MatchResult[]`, `CalculationResult[]` и
`ValidatedRuleSet`, возвращая `QualityControlReport`. Tolerance читается только
из `rule_set.defaults.cost_tolerance_ratio`. Публичный write gate использует
`WriteDecision`, а типизированные находки — `QualityIssueSeverity` и
`QualityIssueCode`. Units не конвертируются, floats,
epsilon и скрытое округление запрещены. Проверяются cardinality/identity,
required values, writable targets, formula cache/Excel errors, provenance,
formula/trace/totals и normalized units. Приоритет: `BLOCK_WRITE`,
`REQUIRE_MANUAL_REVIEW`, `ALLOW_WRITE_WITH_WARNINGS`, `ALLOW_WRITE`.
Issues и IDs сортируются детерминированно. Отчёт содержит safe evidence без raw
cell values, formula text и document content; workbook не изменяется.

## Блок 15.1: formula materialization boundary

`excel_writer/` — отдельная граница записи. Контракт `ExcelWriterContract-15.1`
добавляет numeric-only output: финальные worksheet cells не содержат формул.
Формулы остаются только в immutable source и internal provenance. Decision gate пропускает только
`ALLOW_WRITE` и `ALLOW_WRITE_WITH_WARNINGS`; остальные решения дают
`SKIPPED_DECISION` без output. Writable bindings ровно две: текущие quantity и
cost. Значения — finite `Decimal` без пересчёта, а `None` не очищает ячейку.

Writer выполняет targeted OOXML cell update, не используя `openpyxl.save`.
Если formulas count > 0, LibreOffice headless пересчитывает private temp copy с
isolated profile; при нуле формул пересчёт не запускается. Stale cache после
approved write не используется. Любой unavailable/timeout/error/blank/text или
non-finite result блокирует publication. В output formulas удаляются, а numeric
results сохраняются вместе с форматированием, merged ranges и структурой.
Поддерживается только `.xlsx`; signed OOXML и `.xlsm` отклоняются. Source
identity и fingerprint перепроверяются перед публикацией. Output должен быть
отдельным отсутствующим путём и публикуется атомарно через hard-link
no-clobber; source и существующий output не перезаписываются. CLI отсутствует.

## Модель идентификатора

Обычный файл:

```text
sha256(absolute_path + NUL + size + NUL + modified_time_ns)
```

Запись ZIP:

```text
sha256(absolute_archive_path + NUL + raw_internal_path + NUL + CRC32 + NUL + size)
```

Содержимое многогигабайтных файлов не хешируется. Для ZIP используется исходное
имя `ZipInfo.filename`, даже если отображаемое имя было восстановлено из
ошибочно помеченных UTF-8-байтов. Это сохраняет стабильность `file_id`.

## Provenance

Для обычного файла сохраняются `source_root`, `relative_path`, `filename` и
`file_id`. Для записи ZIP дополнительно сохраняются `archive_path`, CRC32,
сжатый размер и `is_archive_entry=True`.

## Классификация

Классификатор работает только с именем. Unicode приводится к NFKC, `ё` к `е`,
разные тире и разделители унифицируются. Более специфичный тип
`ks2_registry` проверяется раньше общего `ks2`. Комбинированные имена сохраняют
все маркеры, а основной тип выбирается по приоритету.

## Защита ZIP

Сканер:

- вызывает только `ZipFile.infolist()`;
- не вызывает `read`, `open`, `extract` или `extractall` для записей;
- отмечает абсолютные пути, Windows-диски и `..` как `UNSAFE_ARCHIVE_PATH`;
- обрабатывает нулевой сжатый размер без деления на ноль;
- отмечает высокий коэффициент сжатия и записи больше настроенного лимита;
- восстанавливает распространённый случай UTF-8 имени без UTF-8-флага ZIP;
- не переходит к распаковке даже после обнаружения безопасного пути.

## Ошибки

Ошибки источника и сохранения представлены контролируемыми исключениями.
Проблема одной записи отражается в `warnings` и не останавливает весь процесс,
если каталог источника в целом доступен. Повреждённый файл с расширением `.zip`
не обрабатывается как обычный бинарный файл.

## Сериализация

`save_manifest_json` создаёт родительский каталог, записывает UTF-8 JSON во
временный файл, выполняет `flush` и `fsync`, затем заменяет целевой файл через
`os.replace`. При ошибке предыдущая версия результата сохраняется.

`load_manifest_json` проверяет обязательные поля, типы, допустимые статусы и
соответствие `summary.total_entries` длине `entries`.

## Зависимости следующих блоков

Следующий блок должен использовать существующие `FileManifest`,
`FileManifestEntry`, индексные поля, `StatusCode`, идентификаторы и provenance.
Создание второго манифеста или повторное сканирование источника не допускается.

## Индексы документов

`DocumentIndex` хранит исходный фрагмент, каноническую форму и части `main` /
`secondary`. В `FileManifestEntry` добавлены значение, статус, уверенность,
кандидаты и предупреждения; `ManifestSummary` считает подтверждённые,
неоднозначные и низкоуверенные результаты. JSON-сериализация принимает старые
манифесты без этих полей, подставляя `INDEX_NOT_PROCESSED` и нулевые счётчики.

## Блок 13: calculation engine

`calculation/` принимает `MatchResult` и `ValidatedRuleSet`; selected-only:
только `MATCHED` с выбранным кандидатом получает totals. `AMBIGUOUS`/manual
review и `NO_MATCH` остаются без итогов. `Decimal`-поля `period_quantity` и
`period_cost` агрегируются, coefficient применяется к стоимости, затем один
раз выполняется финальный `ROUND_HALF_UP`. Signed negative adjustments
сохраняются с warning; missing — `None`, explicit zero — zero. Float,
non-finite values и unit conversion запрещены. Approved `EXCLUDE` побеждает,
`REVIEW` требует ручного решения, quantity/cost inclusion независимы.

Точные canonical `cost_type_code` дают work/material/service; неизвестный или
отсутствующий код — `UNCLASSIFIED`, без text inference. Result/contribution/
trace IDs — детерминированные SHA-256; trace хранит формулы, coefficient,
quantum, rule IDs, решения, Decimal values, contributing rows и provenance.
Workbook writes отсутствуют.

## Блок 16 — durable audit boundary

`report_processor.audit` изолирует аудит в SQLite с append-only hash chain и
переходами `PENDING → DATA_COMMITTED → EXPORT_PREPARED → EXPORT_VERIFIED`.
Run/report/trace IDs детерминированы; redaction выполняется до сериализации.
JSON/JSONL/CSV exports сортируются, валидируются по SHA/count и публикуются
fsync + hard-link no-clobber; invalid outputs очищаются. Recovery сверяет
data/export hashes и state. Feedback активируется только при `EXPORT_VERIFIED`,
compaction не переписывает events.

Локальный gate: focused **33 passed**, полный real+slow suite
**547 passed in 89.32s**, **583.3 B/event**, append p95 **0.072 ms**;
реальные файлы неизменны. Block 16 принят: PR #16, PR CI `30572493480`, main SHA `ca6300471b52ba1ef80585b3881cb77e04a6be50`, post-merge main CI `30572598426` — success.

## Блок 17 — processing controller (принят в main)

Контроллер отвечает за порядок этапов, типизированный контекст, переходы состояний и адаптеры; бизнес-логика остаётся в Blocks 1–16. API — `process_report` и `process_reports`; CLI — `report-processor process --mode {inspect,dry-run,write}`. Modes: inspect без мутаций, dry-run без публикации, write с QC gate. States: `PENDING`, `RUNNING`, `SUCCEEDED`, `SUCCEEDED_WITH_WARNINGS`, `MANUAL_REVIEW_REQUIRED`, `QUALITY_BLOCKED`, `FAILED`; exit codes `0`–`6`. Resume boundaries: `PENDING`, `DATA_COMMITTED`, `EXPORT_PREPARED`, `EXPORT_VERIFIED` с проверкой хешей и версий контрактов.

Локально подтверждены focused **21 passed**, полный real+slow suite **569
passed in 92.84s**, реальный inspect-контроллер и неизменность обеих XLSX.
PR #17 и CI приняты: PR `30575326764`, post-merge main `30575425467`, main SHA
`322cb9ce08f14c017dbdc3bf16c5b91b33238e63`; полный real+slow — **569 passed in
92.84s**.

## Блок 18 — stage-relation RAG (в работе)

Optional local RAG использует `cointegrated/rubert-tiny2`, revision
`e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae` (29.4M параметров, 312 dimensions,
Russian), lazy local loading без remote API, normalized embeddings/cosine и
deterministic top-k/tie ordering. Missing dependency/model даёт controlled
unavailable без silent matching change. Block 12 rules authoritative; semantic-
only relations требуют manual review. Block 18 tests/model smoke/clean install/
PR/CI пока не подтверждены.
