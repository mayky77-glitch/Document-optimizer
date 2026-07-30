# Мастер-ТЗ: блоки 8–18 и параллельная разработка

Статус: `PLANNING_ONLY` до завершения Gate 0

Дата актуализации: 2026-07-30

Каноническая опубликованная база: `origin/main`, commit `e1c774d`

Рабочий base SHA волны 1: `UNSET` до frozen Gate 0 manifest

## 1. Назначение документа

Документ дополняет краткие ТЗ блоков 8–18 фактическими контрактами проекта,
утверждёнными бизнес-правилами и схемой безопасной параллельной разработки.

Цель: получить единую систему, которая:

- принимает Table 2 и комплект Table 1;
- безопасно читает и нормализует данные;
- применяет версионированные правила;
- показывает пользователю спорные соответствия;
- рассчитывает количество и стоимость только через `Decimal`;
- выпускает одну новую value-only копию Table 2;
- сохраняет полную внутреннюю трассировку;
- не изменяет исходные файлы.

Блоки разрешено разрабатывать в разных чатах. Запрещено превращать их в
отдельные проекты или независимые копии кодовой базы.

## 2. Источники истины

При конфликте требований используется такой порядок:

1. Новое явное решение владельца проекта.
2. Этот мастер-документ.
3. `docs/PRD.md` и `docs/BUSINESS_RULES.md`.
4. `docs/ARCHITECTURE.md` и `docs/ROADMAP.md`.
5. ТЗ отдельного блока.
6. Карточка задачи и переданный агенту prompt.

Для уже реализованного поведения источником истины остаются код и тесты.
Документация не доказывает наличие реализации.

## 3. Фактическая стартовая точка

### 3.1. Канонический код

- `origin/main` на `e1c774d` содержит блоки 1–6 и базовый DuckDB store.
- Чистый локальный эквивалент: worktree `Document-optimizer-duckdb`.
- `Document-optimizer-block07` основан на том же commit, но содержит
  незакоммиченный код блока 7.
- Корневой репозиторий содержит планирование и реальные документы. Он не
  является implementation worktree.
- Старый `Document-optimizer` на `b72070a` нельзя использовать как базу новых
  блоков.

### 3.2. Что уже реализовано частично

- DuckDB schema v1, таблица `canonical_rows`, schema metadata, индексы,
  идемпотентный upsert и JSONL export.
- Классификация строк блока 7.
- Базовая NFKC-нормализация текста, единиц и кодов.
- Существующий `line_id`, который пока включает `source_file_id` и период.
- Provenance исходного файла, листа, строки и ячеек.
- CLI отдельных блоков.

### 3.3. Gate 0 перед блоком 8

До параллельной разработки необходимо:

1. Сохранить dirty diff блока 7 в отдельной ветке.
2. Провести интеграционный review блока 7.
3. Зафиксировать exact integration commit, от которого стартует волна 1.
4. Зафиксировать интерфейс разделения физического `row_id` и бизнесового
   `line_id`. Алгоритм `line_id` реализует блок 8.
5. Создать shared contracts package и зафиксировать версии сериализации.
6. Зафиксировать типы `TargetFormulaSnapshot`, `FormulaCacheState` и полный
   workbook mutation plan Table 2.
7. Зафиксировать минимальные `RunContext` и `AuditEventEnvelope`. Полное
   хранение и feedback memory реализует блок 16.
8. Запустить полный набор тестов и записать baseline.
9. Создать frozen Gate 0 manifest из раздела 18.5.
10. Создать immutable task card для каждого блока текущей волны.

До frozen Gate 0 manifest запрещена production-реализация любого блока 8–18.
Допустимы только read-only анализ и уточнение master contract.

## 4. Неподвижные продуктовые правила

- Расчёт использует только подтверждённый semantic KS-6a и доказанный
  current-cumulative whole-period block.
- Несколько подходящих блоков или файлов не объединяются автоматически.
- Один source row может принадлежать максимум одной строке Table 2.
- Неоднозначность не разрешается случайным выбором.
- Неуверенные решения требуют прямого подтверждения пользователя.
- Unit conversion по умолчанию выключен. Коэффициент конвертации нельзя
  угадывать.
- Внутренние расчёты используют `Decimal`; `float` запрещён.
- Денежная агрегация выполняется в исходных рублях с полной точностью.
- Финальное округление: `ROUND_HALF_UP` до двух знаков там, где это требует
  выходной контракт.
- Исходные Excel не изменяются.
- Итоговый пользовательский файл содержит ноль формул и ноль внешних ссылок.
- Формулы Table 2 заменяются сохранёнными видимыми значениями.
- Формула без cached value блокирует экспорт.
- Стили, merged cells, filters, comments, colors и редактируемость сохраняются.
- Единственный пользовательский результат запуска — новый XLSX Table 2.
- Audit, manifest и feedback memory остаются внутренними локальными данными.

## 5. Общие доменные контракты

### 5.1. Идентификаторы

`row_id` идентифицирует физический экземпляр строки:

- source file;
- sheet;
- row coordinate;
- extraction contract version.

`line_id` идентифицирует бизнес-сущность между файлами и запусками:

- normalization algorithm version;
- scope/stage;
- normalized object и subobject;
- normalized position/basis/drawing/cost-type codes;
- normalized work name;
- normalized unit.

В `line_id` запрещено включать:

- `source_file_id`;
- filename;
- sheet name;
- row number;
- document period;
- quantity;
- cost.

Если данных недостаточно, строка получает низкую `identity_quality`. Система не
подмешивает случайные source coordinates ради уникальности бизнес-ID.
Коллизия сохраняется явно и требует дополнительного контекста или override.

### 5.2. Версионирование

Каждый сохраняемый результат содержит:

- `schema_version`;
- `normalization_version`;
- `identity_version`;
- `rule_set_version`;
- `matching_strategy_version`;
- `calculation_version`;
- `application_version`;
- `run_id`.

Несовместимая major-версия отклоняется контролируемой ошибкой. Миграция не
подменяется молчаливым пересозданием данных.

### 5.3. Provenance

Каждый итог хранит цепочку:

`input hash + file + sheet + row + cells + normalized row + applied rules +
match decision + calculation trace + output cell`.

### 5.4. Ошибки

Все блоки возвращают типизированные:

- result;
- warnings;
- errors;
- stage status;
- audit events.

Необработанный traceback не является публичным контрактом CLI или сайта.

## 6. Блок 8. Бизнес-нормализация и стабильный `line_id`

### Цель

Расширить результаты блока 7 без создания второй конкурирующей нормализации.

### Вход

- фактическая модель блока 7;
- версия normalization profile;
- безопасные alias/typo dictionaries;
- ручные overrides.

### Выход

- `NormalizedSourceRow`;
- `NormalizationTrace`;
- `IdentityQuality`;
- стабильный `line_id`;
- warnings и audit events.

### Нужно реализовать

- вынести общие normalization primitives из `training_data`;
- сохранить compatibility adapter блока 7;
- NFKC, пробелы, регистр, `ё/е`, тире, кавычки и Unicode variants;
- отдельную нормализацию work name, unit и каждого типа кода;
- безопасные scoped dictionaries с ID и версией правила;
- исходное значение рядом с normalized value;
- журнал `field + before + after + rule_id + version`;
- версионированный `line_id` без source-specific полей;
- quality score с reason codes;
- scoped manual override без изменения исходного значения;
- потоковое чтение и запись JSONL;
- CLI без бизнес-логики;
- deterministic order;
- unit, contract и integration tests.

### Не входит

- matching;
- aggregation;
- чтение или запись Excel;
- создание новой DuckDB архитектуры.

### Приёмка

- одинаковая бизнес-строка из разных файлов и периодов получает одинаковый
  `line_id`;
- разные object/scope не склеиваются;
- повторный запуск побитово детерминирован;
- каждое изменение объяснимо через trace;
- старый блок 7 не создаёт вторую модель с тем же смыслом.

Gate 0 владеет только типом identity input/output и version fields. Блок 8
владеет normalization implementation, quality model, hash algorithm и migration
со старого source-specific `line_id`.

## 7. Блок 9. Read-only адаптер целевой Table 2

### Цель

Построить безопасную карту чтения и будущей записи Table 2 без изменения файла.

### Вход

- target XLSX;
- dual workbook session: formula view и data-only view;
- target schema override при подтверждённой неоднозначности;
- выбранные stage и month.

### Выход

- `TargetWorkbookSchema`;
- `TargetReportRow`;
- `TargetPeriodPair`;
- `WritableCellPlan`;
- `TargetFormulaSnapshot`;
- diagnostics и audit events.

### Нужно реализовать

- semantic поиск `Лист1` и допустимых вариантов;
- detection заголовков, object/index blocks и process rows;
- semantic поиск quantity/cost pair выбранного месяца;
- cardinality `0/1/>1` для текущей и предыдущей пары;
- распознавание логических колонок B/E/F/J/K и периодных колонок без жёсткой
  привязки только к буквам;
- чтение existing values и cached formula values;
- сохранение cell coordinates;
- snapshot styles, merges, filters, comments, dimensions и external links;
- allowlist ячеек, которые writer сможет менять;
- диагностику неизвестной или неоднозначной структуры;
- explicit override с fingerprint и версией;
- contract и integration tests на реальном обезличенном Excel.

### Политика формул

Блок 9 только читает и описывает формулы. Он не обещает сохранить формулы в
результате. Блок 15 обязан flatten их в cached values.

`WritableCellPlan` содержит две allowlist:

- `formula_flatten_cells` — все formula cells workbook, которые разрешено
  заменить только их подтверждённым cached visible value;
- `result_write_cells` — target quantity/cost cells, в которые разрешено
  записать расчётный результат.

Если cell входит в обе allowlist, result-write выполняется после flatten и
только при разрешении QC.

Отдельный `StructuralMutationPlan` перечисляет разрешённые изменения структуры:

- создание selected-month quantity/cost pair;
- вставку нужных columns/cells;
- перенос подтверждённых styles, dimensions и merges для новой pair;
- обновление только связанных headers, filters и print ranges.

Отдельный `PackageSanitizationPlan` разрешает:

- удалить external workbook links/connections;
- удалить formula/calc-chain package parts после flatten;
- обновить только обязательные OOXML relationships и content types.

Mutation вне `formula_flatten_cells`, `result_write_cells`,
`StructuralMutationPlan` и `PackageSanitizationPlan` запрещена. Все четыре плана
версионируются, входят в audit и проверяются cell/package diff после reopen.

`FormulaCacheState` различает:

- `NOT_FORMULA`;
- `CACHED_VALUE_PRESENT`;
- `CACHED_BLANK_PRESENT`;
- `CACHE_MISSING`;
- `CACHE_UNTRUSTED`.

Cache определяется по raw OOXML formula/value elements, а не только по
`data_only=True`. Автоматически доказать свежесть cache невозможно. Workbook
recalculation flags, semantic period mismatch или другое доказательство stale
state дают `CACHE_UNTRUSTED` и блокируют export. Recovery: открыть файл в Excel,
пересчитать, сохранить и загрузить заново.

`TargetFormulaSnapshot` — единственное каноническое имя formula contract.

| Cache state | QC | Writer action |
|---|---|---|
| `NOT_FORMULA` | formula-check pass | не flatten |
| `CACHED_VALUE_PRESENT` | pass | записать cached visible value |
| `CACHED_BLANK_PRESENT` | formula-check pass; required-value check отдельно | записать blank |
| `CACHE_MISSING` | `BLOCK_WRITE` | не писать |
| `CACHE_UNTRUSTED` | `REQUIRE_MANUAL_REVIEW`, затем `BLOCK_WRITE` до re-upload | не писать |

Matrix покрывается contract tests. Required blank остаётся отдельным blocker и
не маскируется успешным formula cache check.

### Не входит

- изменение workbook;
- matching;
- calculation;
- автоматический выбор при неоднозначности.

## 8. Блок 10. Конфигурация бизнес-правил

### Цель

Сделать M01–M15 и общие правила типизированными, версионированными и
детерминированными.

### Формат

Канонический MVP-формат — JSON. YAML допускается только как safe-load import,
который сразу преобразуется в тот же канонический JSON contract.

### Вход

- rule-set document;
- schema version;
- optional project override;
- active compatible feedback rules.

### Выход

- `ValidatedRuleSet`;
- `RuleConflictReport`;
- canonical serialization;
- immutable rule-set hash.

### Нужно реализовать

- модели M01–M15;
- object/stage/process scope;
- exact, prefix, exclude и review-only rules;
- exclusive ownership;
- units и unit groups;
- коэффициенты как decimal strings;
- default run coefficient `2.7`;
- rounding и tolerance policies;
- source priority;
- precedence:
  hard exclude, exclusive ownership, approved scoped exact rule, approved
  feedback rule, baseline candidate rule, manual review;
- detection конфликтов и циклов precedence;
- safe parsing, понятные ошибки и canonical dump;
- backwards compatibility policy;
- tests валидных, невалидных и конфликтующих наборов.

### Не входит

- выполнение matching;
- calculation;
- хранение истории feedback;
- UI редактирования правил.

## 9. Блок 11. Аналитический слой DuckDB v2

### Цель

Расширить существующий DuckDB v1. Не создавать второй независимый store.

### Вход

- existing v1 database;
- normalized source rows;
- target rows;
- validated rule-set metadata.

### Выход

- DuckDB schema v2;
- migration v1 to v2;
- repositories;
- analytical views;
- diagnostic export.

### Нужно реализовать

- сохранить существующую `canonical_rows` и совместимость;
- таблицы normalized rows, target rows и rule-set references;
- хранение `row_id`, `line_id`, provenance, versions, warnings и status;
- идемпотентную загрузку через content hash;
- настоящую migration с rollback при ошибке;
- parameterized queries;
- views для diagnostics и candidate preparation;
- schema integrity checks;
- bulk и repeat-run tests;
- performance gate на зафиксированной машине.

### Архитектурная граница

- DuckDB хранит bulk analytical data.
- SQLite хранит transactional run state, feedback memory и append-only audit.
- Matching и calculation работают через repository protocols, а не через
  прямой SQL внутри бизнес-логики.
- Текущий `duckdb_store.py` перед расширением делится на schema, migrations,
  repositories и serialization.

### Не входит

- final matching decision;
- calculation;
- Excel writing;
- feedback history.

## 10. Блок 12. Детерминированный движок сопоставления

### Цель

Связать normalized source rows с process rows Table 2 без случайного выбора.

### Вход

- normalized source rows;
- target rows;
- validated rules;
- compatible active feedback rules;
- repository ports аналитического слоя.

### Выход

- `MatchCandidate`;
- `MatchResult`;
- `MatchExplanation`;
- `MATCHED`, `PENDING_REVIEW`, `AMBIGUOUS`, `UNMATCHED`;
- audit events.

### Каскад

1. Hard exclusions.
2. Exclusive source-row ownership.
3. Exact scoped business keys.
4. Approved M01–M15 exact/prefix rules.
5. Compatible active feedback rule.
6. Deterministic candidate generation.
7. Optional bounded AI suggestion.
8. Explicit user decision для unresolved cases.

### Нужно реализовать

- object/subobject/process scope;
- code, name и unit comparison;
- все M01–M15 границы из `BUSINESS_RULES.md`;
- сохранение всех релевантных кандидатов;
- стабильный score и reason codes;
- configurable candidate limit;
- запрет winner при равном score или недостаточной уверенности;
- manual include/exclude/reassign;
- запрет двойного ownership;
- exact compatibility key для feedback memory;
- contract и integration tests;
- goldens по index 1006 и другим утверждённым fixtures.

### AI-граница

AI может предложить candidate ID и reason code. AI не выбирает файл, не
подтверждает match, не считает суммы и не разрешает экспорт. Невалидный ответ
становится manual review.

## 11. Блок 13. Расчётный движок

### Цель

Рассчитать quantity и cost для каждой target process row с полной lineage.

### Вход

- approved match decisions;
- normalized source rows;
- validated rules;
- selected unit group;
- run-level coefficient.

### Выход

- `CalculationResult`;
- `CalculationTrace`;
- exact и rendered values;
- diagnostics и audit events.

### Нужно реализовать

- только `Decimal`;
- internal cost в raw RUB;
- quantity grouping по normalized unit;
- quantity предпочитает target unit;
- одна alternative unit даёт red `target/source` warning;
- несколько alternative units требуют user selection;
- cost включает все approved rows независимо от выбранной quantity group;
- unit conversion только по explicit versioned rule;
- отрицательные корректировки как явные trace entries;
- coefficient и tolerance branches из `BUSINESS_RULES.md`;
- полную формулу и список source rows;
- stable-order aggregation;
- full precision до output boundary;
- `ROUND_HALF_UP` по выходному контракту;
- отсутствие данных не превращается в synthetic zero;
- unit и integration tests.

### Не входит

- matching;
- QC decision;
- Excel writing.

## 12. Блок 14. Контроль качества и разрешение записи

### Цель

Принять детерминированное решение, разрешён ли экспорт.

### Вход

- match results;
- calculations;
- source и target schemas;
- run decisions;
- warnings всех стадий;
- validated tolerance policy.

### Выход

- `QualityIssue`;
- `QualityControlReport`;
- `ALLOW_WRITE`;
- `ALLOW_WRITE_WITH_WARNINGS`;
- `BLOCK_WRITE`;
- `REQUIRE_MANUAL_REVIEW`.

### Обязательные blockers

- invalid/ambiguous stage или month;
- missing или ambiguous source selection;
- неизвестная target schema;
- `CACHE_MISSING` или `CACHE_UNTRUSTED` нужной формулы;
- pending или ambiguous match;
- duplicate source ownership;
- invalid Decimal;
- unresolved multiple unit groups;
- missing required provenance;
- conflict rule-set versions;
- output cell вне allowlist;
- destination overwrite без подтверждения;
- mismatch, превышающий утверждённый tolerance.

### Нужно реализовать

- severity taxonomy;
- матрицу `issue code + severity + acknowledged` к `WriteDecision`;
- distinction между missing source и valid source с no process candidate;
- duplicate, anomaly, negative и total reconciliation checks;
- deterministic issue ordering;
- machine-readable и user-readable report;
- tests всех переходов решения.

### Не входит

- исправление данных;
- автоматическое подтверждение warning;
- Excel writing.

## 13. Блок 15. Безопасный value-only writer Table 2

### Цель

Создать новую самостоятельную Table 2 без изменения оригинала.

### Вход

- `ALLOW_WRITE` или `ALLOW_WRITE_WITH_WARNINGS`;
- calculations;
- target schema и writable-cell allowlist;
- original target XLSX;
- explicit overwrite confirmations.

### Выход

- новый XLSX;
- `WriteResult`;
- verification report;
- output SHA-256.

### Нужно реализовать

- рабочую копию во временном каталоге;
- formula flatten только в `formula_flatten_cells`;
- запись результатов только в `result_write_cells`;
- semantic reuse/create selected-month quantity/cost pair;
- numeric values, не формулы;
- flatten всех существующих Table 2 formulas через cached visible values;
- blocker, если cached value отсутствует;
- удаление external workbook links/connections;
- сохранение styles, merges, filters, comments, colors, widths и heights;
- atomic save на том же filesystem;
- reopen и structural validation;
- проверку `formula_count == 0`;
- проверку `external_link_count == 0`;
- сверку всех изменённых cells с calculation trace;
- SHA-256 оригинала до и после;
- real sanitized Excel integration tests.

### Не входит

- calculation;
- match selection;
- изменение оригинала;
- LibreOffice recalc;
- macro/formula execution.

## 14. Блок 16. Аудит, run state и feedback memory

### Цель

Обеспечить объяснимость, восстановление запуска и безопасную память решений.

### Порядок реализации

Базовые модели и event API создаются до блока 8. Полная сборка `AuditBundle`
завершается после блока 15.

### Вход

- events всех стадий;
- user decisions;
- hashes и versions;
- calculation и write traces.

### Выход

- internal `RunRecord`;
- `AuditEvent`;
- `TraceReport`;
- `FeedbackRuleVersion`;
- compact active feedback snapshot;
- debug JSONL/CSV export только по явному запросу.

### Нужно реализовать

- единый `run_id` и stage attempt ID;
- append-only audit events;
- input/output SHA-256;
- версии schemas, rules и strategies;
- references на bulk DuckDB data по ID/hash, без копирования всего payload;
- exact user decision before/after;
- feedback activation только после успешного export;
- on/off/restore через новые версии, без физического удаления history;
- compatibility key и context-drift detection;
- local SQLite schema, indexes и migrations;
- redaction конфиденциальных значений;
- retention и compaction без потери lineage;
- crash-safe transactions;
- storage-size и lookup-latency tests.

### Cross-store consistency protocol

SQLite — control plane и источник истины о состоянии запуска. DuckDB хранит
идемпотентные bulk datasets. Распределённая транзакция не имитируется; применяется
явная saga:

1. SQLite создаёт stage attempt со статусом `PENDING`, lease owner и lease
   expiry.
2. DuckDB пишет dataset под `run_id + stage + attempt + content_hash`.
3. SQLite фиксирует `DATA_COMMITTED` и ссылку на dataset hash.
4. Writer создаёт и проверяет временный output.
5. SQLite фиксирует `EXPORT_PREPARED` и ожидаемый output hash/path.
6. Output атомарно переименовывается в final path.
7. SQLite фиксирует `EXPORT_VERIFIED` и только затем активирует feedback rules.

После сбоя recovery читает SQLite state и проверяет dataset/output hashes.
Повтор DuckDB write с тем же content hash идемпотентен. Dataset без SQLite
reference не считается orphan, пока существует active lease.
Feedback никогда не активируется до `EXPORT_VERIFIED`.

Crash-point tests обязательны после каждого шага saga, включая сбой между
final rename и SQLite finalization.

### Recovery и GC

| SQLite state | Проверка | Recovery |
|---|---|---|
| `PENDING` | dataset отсутствует | продлить lease и повторить idempotent write |
| `PENDING` | dataset hash совпадает | зафиксировать `DATA_COMMITTED` |
| `PENDING` | dataset hash отличается | `BLOCKED_STORAGE_INTEGRITY` |
| `DATA_COMMITTED` | dataset hash совпадает | продолжить следующую stage |
| `DATA_COMMITTED` | dataset отсутствует/отличается | `BLOCKED_STORAGE_INTEGRITY` |
| `EXPORT_PREPARED` | temp hash совпадает | verify и atomic rename |
| `EXPORT_PREPARED` | final hash совпадает | зафиксировать `EXPORT_VERIFIED` |
| `EXPORT_PREPARED` | temp/final отсутствуют | пересоздать из `DATA_COMMITTED` |
| `EXPORT_PREPARED` | любой hash отличается | `BLOCKED_OUTPUT_INTEGRITY` |
| `EXPORT_VERIFIED` | final hash совпадает | idempotent feedback activation |
| `EXPORT_VERIFIED` | final отсутствует/отличается | `BLOCKED_OUTPUT_INTEGRITY` |

GC получает exclusive maintenance lock. Dataset удаляется, только если:

- SQLite reference отсутствует;
- active или renewable lease отсутствует;
- owning run terminal или отсутствует;
- истёк versioned `orphan_gc_grace_period`;
- повторная проверка условий выполнена под lock непосредственно перед delete.

Race tests обязательны для concurrent writer/recovery/GC. Hash mismatch никогда
не лечится автоматическим удалением или перезаписью.

### Граница выдачи

Audit остаётся внутренним. Пользователю по умолчанию выдаётся только итоговый
XLSX. Debug export не входит в обычный delivery bundle.

## 15. Блок 17. Главный контроллер, CLI и локальный сайт

### Цель

Связать блоки в один управляемый workflow для пользователя без знания кода.

### Вход

- `ProcessReportRequest`;
- Table 2 XLSX;
- Table 1 folder/ZIP/XLSX;
- stage, month и run options.

### Выход

- `ProcessingResult`;
- итоговый XLSX;
- internal run/audit state;
- стабильные CLI exit codes.

### Нужно реализовать

- `RunContext` и stage state machine;
- inspect, dry-run и write;
- strict и non-strict modes;
- batch только после одиночного стабильного pipeline;
- cache key из input hashes и contract versions;
- безопасный resume с последней подтверждённой стадии;
- cleanup временных файлов;
- единое structured logging;
- CLI как тонкий adapter;
- локальный loopback-only сайт;
- ровно две стартовые upload zones;
- выбор stage и month;
- одна review table;
- direct include/exclude для pending candidates;
- direct on/off switch `Запомнить` без modal;
- live recalculation после решения;
- блокировку export при unresolved state;
- explicit old-to-new overwrite confirmation;
- Host/Origin/CSRF и cross-session protection;
- pipeline E2E tests.

### Exit-code группы

- success;
- success with warnings;
- invalid input;
- ambiguous/manual review required;
- quality blocked;
- write/verification failed;
- internal controlled error.

## 16. Блок 18. Финальная интеграция и release gate

### Цель

Проверить не набор блоков, а одну устанавливаемую систему.

### Нужно реализовать и проверить

- отсутствие duplicate domain models;
- отсутствие cyclic imports;
- compatibility всех versions и serializers;
- clean install в новом окружении;
- полный pipeline через CLI и сайт;
- E2E и golden tests;
- goldens для index 1006;
- sanitized real-data corpus;
- original hashes unchanged;
- deterministic repeated run;
- migration v1 to v2;
- resume after controlled failure;
- performance и memory budgets;
- zero formulas/external links в output;
- one-file user delivery;
- audit/feedback integrity;
- package contents и licenses;
- user runbook;
- final integration report;
- release archive, checksums и повторная проверка после unpack.

### Не входит

- новые features;
- исправление требований прямо во время release;
- production/cloud deployment;
- передача реальных конфиденциальных fixtures.

## 17. DAG и волны разработки

```text
Gate 0: integrated Block 7 + shared contracts + frozen handoff manifest

Wave 1: Block 8 | Block 9 | Block 10
Wave 2: Block 11 | Block 16 core persistence | Block 12 design only
Wave 3: Block 12 | Block 16 stage instrumentation
Wave 4: Block 13 | Block 15 writer shell only
Wave 5: Block 14, затем полная integration Block 15
Wave 6: complete Block 16, затем Block 17
Wave 7: Block 18
```

Допускается максимум три параллельных write-потока. Больше потоков увеличивает
число конфликтов быстрее, чем скорость разработки.

### 17.1. Обязательные prerequisites

- Block 8: frozen Gate 0 manifest.
- Block 9: frozen Gate 0 manifest.
- Block 10: frozen Gate 0 manifest.
- Block 11: принятые commits блоков 8, 9 и 10.
- Block 12 design: frozen contracts блоков 8, 9, 10 и 11.
- Block 12 production merge: принятый commit блока 11.
- Block 13: принятые commits блоков 10 и 12.
- Block 14: принятые commits блоков 9, 10, 12 и 13.
- Block 15 writer shell: принятый commit блока 9; merge shell запрещён до
  frozen calculation/QC contracts.
- Block 15 full integration: принятые commits блоков 13 и 14.
- Block 16 core: frozen `RunContext`, `AuditEventEnvelope` и cross-store
  protocol из Gate 0.
- Block 16 feedback integration: принятые commits блоков 10, 12 и 15.
- Block 17: принятые commits блоков 8–16.
- Block 18: integrated blocks 1–17 и ноль открытых critical findings.

Design-only работа не получает production write scope и не может быть влита
как feature implementation.

## 18. Схема работы в разных чатах

### 18.1. Главный интеграционный чат

Единственный владелец:

- canonical base SHA;
- master spec;
- contract freeze;
- task cards;
- write-scope reservations;
- merge order;
- full regression;
- финальный audit волны;
- release branch.

Главный чат не раздаёт всем агентам весь проект одновременно. Он запускает
только текущую волну.

### 18.2. Чат отдельного блока

Получает:

- номер и цель блока;
- exact base SHA;
- dependency commits;
- разрешённые source paths;
- разрешённые test paths;
- frozen input/output contracts;
- acceptance commands;
- branch name;
- запрещённые действия.

Чат блока обязан:

1. Создать worktree/branch от указанного SHA.
2. Проверить фактические предыдущие модели.
3. Не создавать дубли domain models, CLI и serialization.
4. Менять только зарезервированные paths.
5. Добавить unit, contract и integration tests.
6. Запустить focused tests, затем полный regression.
7. Обновить документацию своего блока.
8. Сделать commit и push своей feature branch.
9. Передать commit SHA, diff summary, tests и известные риски.
10. Не сливать ветку самостоятельно.

### 18.3. Имена веток

Пример:

- `codex/block-08-normalization`;
- `codex/block-09-target-adapter`;
- `codex/block-10-rule-config`;
- `codex/integration-wave-01`.

### 18.4. Запрещено

- создавать новый репозиторий под блок;
- копировать весь проект вручную;
- стартовать от локальной устаревшей `main`;
- менять shared model без contract task;
- расширять scope по собственной инициативе;
- коммитить реальные Excel или `.env`;
- отдавать внешний AI приватный код или документы;
- делать ZIP после каждого блока;
- параллельно менять один файл из разных чатов.

### 18.5. Frozen Gate 0 manifest

Главный чат создаёт `docs/handoffs/GATE0.md` со всеми заполненными полями:

```text
status: FROZEN
published_base_sha: e1c774d
block_07_sha: <exact commit>
wave_01_base_sha: <exact integration commit>
shared_contract_sha: <exact commit>
schema_versions: <exact mapping>
formula_policy_version: <version>
audit_envelope_version: <version>
baseline_commands: <exact commands>
baseline_results: <counts and date>
shared_paths_owner: integration chat
created_at: <ISO-8601>
```

Manifest с `UNSET`, placeholder или dirty dependency запрещает запуск block
chat. Изменение frozen manifest создаёт новую version и новый wave base SHA.

### 18.6. Immutable block task card

Перед запуском каждого block chat главный чат создаёт отдельную карточку со
всеми заполненными полями шаблона раздела 19. Канонический path:
`knowledge/tasks/<work-id>-block-<NN>-<slug>.md`.

Обязательные metadata:

- `card_id`;
- `status: frozen`;
- `version`;
- `supersedes` или `null`;
- `work_id`;
- `card_path`;
- `base_sha`;
- `dependency_shas`;
- `write_scope`;
- `forbidden_paths`;
- `contract_versions`;
- `acceptance_commands`.

Integration chat коммитит карточку и передаёт block chat отдельный
`card_commit_sha`. Это Git commit, содержащий exact frozen card; self-referential
SHA внутри карточки не используется. Block chat до работы проверяет, что
`git show <card_commit_sha>:<card_path>` побитово совпадает с рабочей карточкой.
Несовпадение, missing path, status не `frozen` или superseded card требуют
отказа от запуска.

После запуска запрещено менять:

- base SHA;
- dependency SHAs;
- write scope;
- required contract versions;
- acceptance commands.

Изменение любого поля supersedes старую карточку и требует новую ветку или
явно проверенный rebase до handoff.

### 18.7. Shared paths

Только integration chat меняет shared wiring:

- package-level `__init__.py` exports;
- общий `cli.py` command registry;
- shared contracts;
- dependency configuration;
- integration status и wave manifest.

Block chat создаёт собственный module и собственный `cli_<block>.py`, но не
подключает его параллельно в общий registry. Это выполняется при интеграции.

## 19. Шаблон задания для нового чата

Шаблон нельзя передавать агенту с незаполненными placeholders. Runnable task
существует только как frozen card из раздела 18.6.

```text
Ты реализуешь Block <N>: <name>.

Card ID: <exact card_id>
Card version: <version>
Card status: frozen
Card path: knowledge/tasks/<work-id>-block-<NN>-<slug>.md
Card commit SHA: <commit containing exact card>
Supersedes: <card_id or null>
Project root: <absolute worktree path>
Base commit: <exact SHA>
Branch: codex/block-<NN>-<slug>
Master spec: docs/MASTER_PLAN_BLOCKS_08_18.md
Canonical product rules: docs/PRD.md, docs/BUSINESS_RULES.md

Dependencies already integrated:
- <commit and contract list>

Your exclusive write scope:
- src/report_processor/<paths>
- tests/<paths>
- docs/<block document>

Forbidden paths:
- <shared paths owned by other chats>

Required input contracts:
- <types + schema versions>

Required output contracts:
- <types + schema versions>

Acceptance:
- <focused commands>
- ruff check .
- full pytest
- source file hashes unchanged where relevant

Rules:
- verify frozen card against Card commit SHA before any work;
- refuse on placeholder, mismatch, superseded card or dirty dependency;
- inspect actual code/tests before changes;
- do not duplicate models, enums, serialization or CLI;
- no unrelated refactor;
- no real confidential fixtures;
- commit and push feature branch;
- return SHA, changed paths, tests, evidence and risks;
- do not merge.
```

## 20. Интеграция каждой волны

Главный чат выполняет:

1. Проверку branch base и scope.
2. Read-only review каждого diff.
3. Проверку `merge-base --is-ancestor <wave-base> <feature-sha>`.
4. Проверку, что feature SHA ещё не интегрирован.
5. `git merge --no-ff` в dependency order. Cherry-pick запрещён.
6. Исправление только доказанных contract conflicts.
7. Contract tests между блоками.
8. Полный `ruff check .` и `pytest`.
9. Relevant real-data gate с неизменностью hashes.
10. Один финальный architecture/correctness audit волны.
11. Обновление master status и нового integration SHA.
12. Push integration branch.

Следующая волна стартует только от нового проверенного integration SHA.

После передачи feature SHA запрещены force-push, amend и rebase этой ветки.
До handoff rebase допустим только на exact wave base с повторным полным
acceptance. При конфликте integration chat возвращает finding владельцу блока;
скрыто переписывать feature history запрещено.

## 21. Definition of Done отдельного блока

Блок готов, только если:

- input/output contract типизирован и версионирован;
- нет дублирования существующих моделей;
- happy path и ошибки покрыты;
- unit, contract и integration tests проходят;
- результат детерминирован;
- audit events присутствуют;
- документация соответствует коду;
- нет файла production-кода больше 700 строк;
- файлы около 500 строк проверены на декомпозицию;
- branch закоммичен и запушен;
- integration chat принял доказательства.

## 22. Definition of Done всей системы

Система готова, когда:

- блоки 1–17 работают одной цепочкой;
- пользователь проходит workflow без знания кода;
- каждый итог объясним до source cells;
- unresolved ambiguity блокирует export;
- итоговый XLSX value-only, редактируемый и автономный;
- исходные hashes неизменны;
- повторный запуск детерминирован;
- feedback memory versioned и обратима;
- clean install и release archive повторно проверены;
- Block 18 integration report не содержит открытых critical findings.

## 23. Практическое решение по «орде агентов»

Разумная модель — не одиннадцать автономных чатов, а управляемая очередь:

- один главный интеграционный чат;
- до трёх блоковых чатов текущей волны;
- один read-only reviewer после интеграции волны;
- новый SHA перед следующей волной.

Так сохраняется ускорение параллельной разработки, но контракты и данные не
расходятся между копиями проекта.
