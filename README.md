# Document Optimizer

Python-проект для поэтапной обработки строительных отчётов КС-2, КС-3, КС-6а,
СВВР, допотчётов и связанных документов.

## Текущий статус

В integration-ветке реализованы **блоки 1–14 — от инвентаризации источников до
детерминированного quality-control write gate** (текущая версия пакета `0.8.0`).
Локальный release-набор блока 14 прошёл: Ruff, format, clean install, compileall
и **490 pytest-тестов**. Real-data gate использовал две существующие книги Excel
без изменения их SHA-256, размера и `mtime`; quality-control вернул
`REQUIRE_MANUAL_REVIEW` без blocking issues. GitHub CI остаётся обязательным
gate перед merge в `main`.
Проект принимает каталог, отдельный файл или ZIP-архив и строит типизированный
JSON-манифест без чтения содержимого Excel и без распаковки ZIP. Блок 2
обогащает готовый `FileManifest` индексами вида `1006 (682)` по имени и
относительному пути; повторное сканирование источника не требуется.

Состояние блоков и результаты проверок приведены в
[`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

## Требования

- Python 3.12 или новее;
- стандартная библиотека для работы приложения;
- `pytest` и `ruff` только для разработки.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

В Windows активация окружения выполняется командой:

```powershell
.venv\Scripts\Activate.ps1
```

## Запуск инвентаризации

Каталог:

```bash
python -m report_processor.cli inventory \
  --source "/path/to/folder" \
  --output "cache/file_manifest.json"
```

ZIP-архив:

```bash
python -m report_processor.cli inventory \
  --source "/path/to/archive.zip" \
  --output "cache/archive_manifest.json"
```

Нерекурсивный обход каталога:

```bash
python -m report_processor.cli inventory \
  --source "/path/to/folder" \
  --no-recursive
```

Инвентаризация с индексами:

```bash
python -m report_processor.cli inventory \
  --source "/path/to/folder" \
  --output "cache/indexed_manifest.json" \
  --extract-indexes
```

Обогащение ранее сохранённого манифеста:

```bash
python -m report_processor.cli extract-indexes \
  --manifest "cache/file_manifest.json" \
  --output "cache/indexed_manifest.json"
```

Обогащение периодами и редакциями, затем выбор источника:

```bash
python -m report_processor.cli enrich-metadata \
  --manifest "cache/indexed_manifest.json" \
  --output "cache/metadata_manifest.json"

python -m report_processor.cli select-source \
  --manifest "cache/metadata_manifest.json" \
  --index "1006 (682)" \
  --period "2026-07" \
  --preferred-types "ks6a,ks2" \
  --allowed-types "ks6a,ks2" \
  --json-output "cache/selection.json"
```

Поддерживаемые параметры:

- `--source` — каталог, файл или ZIP;
- `--output` — путь JSON-манифеста;
- `--recursive` / `--no-recursive` — режим обхода каталога;
- `--extract-indexes` — добавить индексы при инвентаризации;
- `--use-parent-paths` / `--no-use-parent-paths` — учитывать каталоги пути при
  отдельном обогащении;
- `--allow-loose` — добавить низкоуверенные кандидаты с разделителями вместо
  скобок;
- `--log-level` — `DEBUG`, `INFO`, `WARNING`, `ERROR` или `CRITICAL`.

## Публичный Python API

```python
from pathlib import Path

from report_processor import (
    build_file_manifest,
    classify_file_by_name,
    load_manifest_json,
    save_manifest_json,
    scan_directory,
    scan_zip_archive,
)
from report_processor.identifiers import extract_document_index

manifest = build_file_manifest(Path("/path/to/source"))
save_manifest_json(manifest, Path("cache/file_manifest.json"))
restored = load_manifest_json(Path("cache/file_manifest.json"))
index = extract_document_index("1006 (682)_КС-2.xlsx")
```

Основные модели:

Блок 8 публикует `NormalizedSourceRow`, `NormalizedBusinessKey`,
`NormalizationConfig` и `NormalizationResult`. Вход — `TrainingDataRow` схемы
`7.0`; CLI — `report-processor normalize-rows`; выход — JSONL схемы `8.0`.
Provenance и `Decimal` сохраняются, business `line_id` не зависит от physical
source. Exact typo dictionaries являются data-only конфигурацией.

- `FileManifestEntry` — provenance и классификация одного файла;
- `ManifestSummary` — агрегированная статистика;
- `FileManifest` — источник, записи, сводка и версия схемы;
- `StatusCode` — единый набор статусов и предупреждений.

## Формат манифеста

JSON сохраняется в UTF-8, содержит ISO 8601 даты и записывается атомарно через
временный файл и `os.replace`. Для каждой записи сохраняются:

- стабильный технический `file_id`;
- корень источника и относительный путь;
- размер, дата изменения и ZIP-метаданные;
- тип документа и все обнаруженные маркеры;
- признаки временного файла, копии и устаревшей версии;
- статус и машинно-читаемые предупреждения.
- необязательные индекс, период, редакция и признаки статуса имени;
- отдельный результат выбора с обоснованием, рейтингом и отклонениями.

ZIP читается только через центральный каталог `ZipFile.infolist()`. Содержимое
записей не читается и не извлекается. Определяются ZIP Slip, подозрительное
сжатие, очень большие записи и устаревшие ZIP-имена, где UTF-8-байты были
записаны без UTF-8-флага.

## Проверки

```bash
ruff check .
pytest
pytest tests/unit
pytest tests/contract
pytest tests/integration
```

CI выполняет `ruff check .` и полный `pytest` на Python 3.12.

## Блок 5: распознавание структуры Excel

`detect-schema` безопасно использует выбранный файл и read-only сессию блока 4,
чтобы классифицировать листы, ограниченно просканировать заголовки, разрешить
логические столбцы и атомарно сохранить JSON-описание. Книга не изменяется.

```bash
report-processor detect-schema --selection output/source_selection.json \
  --output output/workbook_schema.json
```

## Блок 6: извлечение канонических строк

`extract-rows` потоково читает распознанные листы КС-2, КС-6а и СВВР,
сохраняет формулы и provenance ячеек в DuckDB — основной рабочий выход по
умолчанию. Исходный Excel не изменяется.

```bash
report-processor extract-rows \
  --selection output/source_selection.json \
  --schema output/workbook_schema.json \
  --output output/extracted_rows.duckdb
```

Публичные адаптеры поддерживают КС-2, КС-6а и СВВР. Строки содержат исходные,
кэшированные и формульные значения, а также provenance источника и ячейки.
Команда принимает манифест или selection, схему и output; доступны фильтры
листа и типа, лимиты и форматы DuckDB/JSONL/JSON. JSONL и JSON остаются
явно выбираемыми форматами экспорта и аудита: `--format jsonl` или `--format json`.
Неразрешённые или не-OK столбцы
пропускаются; при неопределённой схеме или отсутствии поддерживаемого листа
возвращается контролируемый нулевой результат либо отказ на ручную проверку,
без угадывания. Формулы не вычисляются, а текст `ArrayFormula` нормализуется.

## Блок 7: подготовка данных для обучения

`prepare-training-data` принимает основной DuckDB блока 6 или совместимый JSONL,
классифицирует строки, нормализует текст, единицы и коды, исключает итоговые,
неактуальные и критически повреждённые строки, затем атомарно сохраняет
`TrainingDataRow` JSONL с метаданными.

```bash
report-processor prepare-training-data \
  --input output/extracted_rows.duckdb \
  --output output/training_rows.jsonl
```

Формат определяется по `.duckdb`/`.jsonl`; для нестандартного расширения задайте
`--input-format duckdb` или `--input-format jsonl`. Формулы с корректным
кэшированным значением не считаются ошибкой. Точные семантические дубли удаляются;
конфликтующие строки сохраняются с новым ID и предупреждением. Входной DuckDB
открывается только для чтения; все числовые поля, включая `total_cost`,
сохраняются, а `NaN`/`Infinity` отклоняются.

## Блок 13: расчёт по принятым сопоставлениям

Блок 13 публикует `CalculationContract-13.0` и `CalculationEngine-13.0`.
`calculate_matches(match_results, rule_set)` учитывает только `MATCHED` с
выбранным кандидатом; `AMBIGUOUS`/manual review и `NO_MATCH` не получают
итогов. Количество и стоимость — конечные `Decimal` из `period_quantity` и
`period_cost`; коэффициент применяется к стоимости, затем один раз выполняется
финальный `ROUND_HALF_UP`. Signed negative adjustments сохраняются с trace
warning, missing остаётся `None`, explicit zero сохраняется; float, non-finite
values и unit conversion запрещены.

Только approved rules участвуют: `EXCLUDE` побеждает, `REVIEW` требует ручного
решения, включение quantity и cost независимо. Категории `work`, `material` и
`service` определяются только точным canonical `cost_type_code`; неизвестный
или отсутствующий код остаётся `UNCLASSIFIED`, без вывода по тексту.
Результаты и вклады имеют детерминированные SHA-256 ID, полный formula trace и
provenance. Workbook не изменяется. Focused gate: **11 passed**; полный suite:
**482 passed**. Real-data gate: **1 calculated**, **5 manual_review**,
**101 no_match**, все рассчитанные вклады — `UNCLASSIFIED`; digest
`6b814337cb55e574cae7ab42bf9c4d81af99bc163067d76c31d56085c4ee8d54`.
Обе исходные XLSX остались неизменны. Статус `main` и CI фиксируются только
после успешного Pull Request.

## Блок 14: quality-control write gate

Публичный API блока 14: `evaluate_quality_control(match_results, calculation_results, rule_set) -> QualityControlReport`.
Публичные типы решений и находок: `WriteDecision`, `QualityIssueSeverity`,
`QualityIssueCode`, `QualityLocation`, `QualityIssue` и `QualityControlSummary`.
`ValidatedRuleSet.defaults.cost_tolerance_ratio` — единственный источник tolerance.
Проверяются cardinality/identity, provenance, trace/totals, formula cache и Excel
errors, required values, writable targets, normalized units и Decimal tolerance.
Решения имеют precedence: `BLOCK_WRITE` → `REQUIRE_MANUAL_REVIEW` →
`ALLOW_WRITE_WITH_WARNINGS` → `ALLOW_WRITE`. IDs и digest детерминированы;
raw cells, formula text и document content в отчёт не копируются. Workbook read-only.

Проверенное локальное evidence: synthetic set — 7 PASS; real-data —
`REQUIRE_MANUAL_REVIEW`, 0 blocking issues, digest
`c20ecd6839a44cfb90586858f9a7699180f28fde2f299819624c2d3606689492`.
Полный release-suite: **490 passed**; Ruff, format, clean install, compileall и
`git diff --check` — PASS. Обе исходные XLSX неизменны. Статус `main` и CI
фиксируются только после успешного Pull Request.
Входные XLSX не изменились. Это не объявляет READY/main или CI.

## Ограничения блоков 1–7

Намеренно не реализованы:

- сопоставление документов и работ;
- расчёты количества и стоимости;
- автоматическое построение train/test split и обучение моделей;
- Parquet и pandas;
- изменение или полная распаковка исходных файлов;
- код следующих блоков.

Жизненный цикл чтения остаётся read-only для `.xlsx`/`.xlsm` и выбранной ZIP-записи.
DuckDB schema v1 выполняет транзакционный idempotent upsert по `row_id`; миграции
предыдущих схем пока не поддерживаются, а более новая схема открывается с
контролируемой ошибкой. `DuckDBStore` владеет соединением: используйте контекстный
менеджер или вызовите `close()`. Запросы имеют equality-фильтры по source file,
индексу, периоду и типу. Потоковый JSONL и `*.meta.json` записываются атомарно и
допускают восстановление; JSON-вывод использует тот же безопасный подход.

Архивные даты ZIP не содержат часовой пояс по формату ZIP, поэтому сохраняются
как локальные наивные значения. Полный хеш содержимого больших файлов не
вычисляется: `file_id` является техническим идентификатором метаданных.

Индекс извлекается только из имени и относительного пути, без открытия Excel.
Шаблон по умолчанию строгий: `main (secondary)`, а неоднозначные, похожие на год
и loose-кандидаты не выдаются как подтверждённый индекс.

## Архитектура

Модули и границы ответственности описаны в
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Блоки 9–11 интегрированы в `main`. Блок 12 реализован в integration-ветке;
PR, CI и merge в `main` остаются отдельным release gate.

## Блок 9: чтение целевого отчёта

```bash
report-processor read-target-report \
  --source "/path/to/report.xlsx" \
  --schema output/target_schema.json \
  --output output/target_report.json
```

Команда формирует `TargetReportSchema-9.0`, канонические строки, snapshots
формул/кэша и provenance. `WritableCellPlan` только описывает допустимые ячейки
и не применяется этим блоком. Ненадёжный кэш формул и неоднозначный выбор
возвращаются на ручную проверку. Исходная книга не изменяется.

## Блок 10: data-only бизнес-правила

```bash
report-processor validate-business-rules \
  --config config/business_rules.yaml \
  --output output/business_rules.json
```

Поддерживаются JSON/YAML data-only конфигурации. Дубликаты YAML-ключей,
tags, anchors/aliases и исполняемые конструкции отклоняются. Валидатор
сохраняет `Decimal`, precedence, scope, политики количества/стоимости,
структурированные конфликты M01–M15, canonical JSON и SHA-256.

## Блок 11: аналитический DuckDB

`report_processor.analytics.AnalyticalStore` — отдельное аналитическое хранилище
DuckDB. Оно принимает `NormalizedSourceRow`, `TargetReportRow` с явными
`target_source_id` и `target_fingerprint`, а также `ValidatedRuleSet`; рабочий
`DuckDBStore` блока 6 не открывается и не изменяется.

Схема `AnalyticalSchema-1` создаёт таблицы источников, целей, правил, clauses и
warnings, служебную metadata и views `v_source_rows`, `v_target_rows`,
`v_rule_clauses`, `v_diagnostics`. Загрузка идемпотентна; конфликт payload для
существующего идентификатора откатывает транзакцию. Named queries ограничены
фиксированным allowlist и параметризованными значениями. Диагностика
экспортируется детерминированно в JSONL атомарной заменой файла. Сопоставление
и бизнес-логика блока 12 сюда не входят.

Real-data gate на исходных XLSX загрузил 382 нормализованные source rows,
107 target rows и 34 rule clauses. Повторная загрузка дала только unchanged;
SHA-256, размер и `mtime` обеих книг до/после совпали.

## Блок 12: детерминированное сопоставление строк

`report_processor.matching.match_rows` сопоставляет `NormalizedSourceRow` с
`TargetReportRow` по семи стратегиям в фиксированном порядке: точный
бизнес-ключ, индекс и позиция, объект/подобъект/позиция, нормализованное
наименование и единица, наименование и контекст, подтверждённое правило,
fuzzy-кандидат для ручной проверки.

API возвращает все `MatchCandidate` с provenance и один `MatchResult` на
целевую строку. Выбор определяется ordinal стратегии, а не confidence.
Равенство лучших кандидатов даёт `AMBIGUOUS`; fuzzy-only и `REVIEW` никогда
не выбираются автоматически, `EXCLUDE` блокирует кандидата. Учитываются только
правила с `owner_approved=true` и `status=approved`. Денежные вычисления и
запись Excel в блок не входят.

Real-data gate на двух исходных книгах обработал 382 source rows и 107 target
rows: 1 matched, 5 ambiguous, 101 unmatched, 35 сохранённых кандидатов.
Повторный прогон с обратным порядком входов дал тот же SHA-256 результата;
SHA-256, размер и `mtime` обеих книг не изменились.
