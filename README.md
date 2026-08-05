# Document Optimizer

Python-проект для поэтапной обработки строительных отчётов КС-2, КС-3, КС-6а,
СВВР, допотчётов и связанных документов.

## Текущий статус

В `main` приняты **блоки 1–18** — от безопасной инвентаризации до единого
processing controller, numeric-only XLSX publication и append-only audit.
Версия пакета — `1.0.0`. Блок 18 добавляет локальные RuBERT-подсказки,
финальные release-gates и простую локальную web-панель.
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

## Установка и запуск (Windows, macOS и Linux)

Ниже приведён рекомендуемый путь для первого запуска локальной панели. Все
команды выполняются из корня проекта — папки, где одновременно лежат
`pyproject.toml`, `start-admin.cmd`, `start-admin.command` и `start-admin.sh`.

### 1. Что установить заранее

- Python **3.12 или новее** (проверьте: `python --version`; в Windows может
  понадобиться команда `py --version`);
- `uv` — менеджер окружений и зависимостей. Инструкция для Windows, macOS и
  Linux: <https://docs.astral.sh/uv/getting-started/installation/>. Проверьте
  установку командой `uv --version`.

Git не обязателен: вместо клонирования можно скачать ZIP-архив репозитория и
распаковать его в удобную папку.

### 2. Скачать проект и перейти в его корень

При использовании Git:

```bash
git clone https://github.com/mayky77-glitch/Document-optimizer.git
cd Document-optimizer
```

Если проект скачан ZIP-файлом, распакуйте его и перейдите в распакованную
папку. Убедитесь, что файл `pyproject.toml` виден в текущем каталоге:

```bash
# macOS/Linux
pwd && ls pyproject.toml

# Windows PowerShell
Get-Location; Get-ChildItem pyproject.toml
```

### 3. Рекомендуемый запуск панели

Лаунчеры сами переходят в папку проекта, проверяют `uv`, выполняют
`uv sync --extra rag` и запускают `report-processor admin`:

- Windows: дважды откройте `start-admin.cmd` (или запустите его из PowerShell);
- macOS: откройте `start-admin.command` двойным щелчком. Если macOS блокирует
  файл, разрешите запуск в **Системные настройки → Конфиденциальность и
  безопасность**, либо используйте команду из терминала ниже;
- Linux: выполните `./start-admin.sh`. При необходимости сначала задайте право
  запуска: `chmod +x start-admin.sh`.

### 4. Запуск из терминала (универсальный вариант)

Из корня проекта выполните:

```bash
uv sync --extra rag
uv run report-processor admin
```

Опция `--extra rag` устанавливает зависимости локального RAG. В
`pyproject.toml` также доступны `--extra dev` (pytest, ruff) и независимый
`--extra rag`; для обычного запуска панели достаточно `rag`.

После старта откройте в браузере:

- проверка документов: <http://127.0.0.1:8765/>;
- составление отчёта об остатках с автосверкой: <http://127.0.0.1:8765/drawing-card>;
- сравнение Excel или LibreOffice Calc с PDF-отчётами (PDF АОСР — дополнительно): <http://127.0.0.1:8765/package-reconciliation>;
- справка по выбору процесса: <http://127.0.0.1:8765/help>.

Панель работает только на этом компьютере (loopback) и не публикуется в сеть.
Если веса `cointegrated/rubert-tiny2` ещё не загружены, правила продолжат
работать без semantic RAG. Однократная загрузка модели описана ниже в разделе
«Блок 18».

На странице **«Проверка документов»** исходные книги автоматически
сопоставляются с выбранным отчётом. Если расхождений нет, панель показывает
сообщение «Все документы проверены. Ошибок не найдено.». Если строки не прошли
проверку, оригиналы остаются неизменными, а для скачивания создаются отдельные
копии Excel, где проблемные физические строки выделены красным. При нескольких
исходных книгах копии собираются в один ZIP.

Страница **«Составление отчёта»** создаёт или обновляет карточку остатков.
Автосверка входит в процесс: однозначные строки обрабатываются сразу, а ручное
решение запрашивается только для неопределённых соответствий.

### Если появляется `No pyproject.toml`

Сообщение означает не отсутствие файла в проекте, а то, что команда `uv sync`
запущена не из корня (например, из `Downloads` или из каталога `src`).
Перейдите в каталог, где лежит `pyproject.toml`, и повторите команды:

```bash
cd /путь/к/Document-optimizer-ready
uv sync --extra rag
uv run report-processor admin
```

Лаунчеры из шага 3 делают этот переход автоматически.

### Остановка, повторный запуск и обновление

- Для остановки запущенной панели вернитесь в окно терминала и нажмите
  `Ctrl+C`. При запуске двойным щелчком закройте окно после остановки процесса.
- Для повторного запуска снова выполните `uv run report-processor admin` или
  откройте соответствующий launcher.
- Для обновления исходников через Git остановите панель, затем выполните:

  ```bash
  git pull
  uv sync --extra rag
  uv run report-processor admin
  ```

  При установке из ZIP скачайте и распакуйте свежий архив в новую папку.
  Нужные готовые результаты сохраните отдельно; приватный временный каталог
  `.admin-panel-jobs/` переносить не нужно.

## Сравнение Excel с PDF-отчётами

В панели есть и папочный вариант этой проверки: откройте
`http://127.0.0.1:8765/package-reconciliation`, выберите одну папку с таблицами
`.xlsx`, `.xlsm` или LibreOffice Calc `.ods`, затем скачайте JSON-отчёт после
завершения. PDF АОСР можно добавить дополнительно для
документальных доказательств: без PDF проверка Excel всё равно выполняется, а
строки без доказательства получают `NO_EVIDENCE`. Панель передаёт структуру
выбранной папки только локальному сервису; абсолютные пути и сырой OCR в отчёт
не попадают. Значения `MATCH` и `MISMATCH` означают, что сопоставление найдено;
`AMBIGUOUS`, `NO_EVIDENCE` и `NEEDS_REVIEW` требуют ручной проверки. Подробнее
о трёх процессах, допустимых файлах и восстановлении после ошибок — на странице
`http://127.0.0.1:8765/help`.

Команда ниже сверяет строки КС-2 с актами АОСР, лежащими внутри одного пакета:

```bash
uv run report-processor reconcile-package \
  --package "/путь/к/пакету" \
  --output "/путь/к/существующей/папке/report.json"
```

Для сканированных PDF должны быть установлены Poppler (`pdfinfo`, `pdftotext`,
`pdftoppm`) и Tesseract с языками `rus` и `eng`. Обработка полностью локальная:
OCR ограничен первыми двумя страницами подходящих АОСР, исходные Excel и PDF не
изменяются. В JSON записываются только относительные пути и структурированные
результаты; сырой OCR, формулы и абсолютные пути не сохраняются. Права файла
результата — `0600`.

Статусы `MATCH` и `MISMATCH` означают подтверждённое сопоставление; `AMBIGUOUS`,
`NO_EVIDENCE` и `NEEDS_REVIEW` требуют ручной проверки. Совпадение одного имени
файла никогда не считается достаточным доказательством.

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
Входные XLSX не изменились. Block 16 принят в `main`: PR #16, PR CI run `30572493480` и post-merge main CI `30572598426` успешны; main SHA `ca6300471b52ba1ef80585b3881cb77e04a6be50`. Полный real+slow suite: **547 passed in 89.32s**.

## Блок 17: processing controller (принят в main)

Frozen contracts: `ProcessingContract-17.0`, `ProcessingEngine-17.0`, `ProcessingState-17.0`. API: `process_report(request) -> ProcessingResult`, `process_reports(requests) -> tuple[ProcessingResult, ...]`; CLI: `report-processor process --mode {inspect,dry-run,write}`. Modes: inspect без DuckDB/XLSX output, dry-run без Block 15 publication, write с QC-gated публикацией. States: `PENDING`, `RUNNING`, `SUCCEEDED`, `SUCCEEDED_WITH_WARNINGS`, `MANUAL_REVIEW_REQUIRED`, `QUALITY_BLOCKED`, `FAILED`. Exit codes: 0–6 для success, warnings, invalid input, manual review, quality blocked, write/verification failed и controlled internal error.

Локальный gate: focused **21 passed**, полный real+slow suite **569 passed in
92.84s**; реальный `process --mode inspect` прошёл контроллер Blocks 1–16.
SHA-256 исходной и целевой XLSX остались
`556454e5c087f1728c994b2888191644f04d29d48fbd2a29e9aa136cf1ab0698` и
`5b38ed6650aa5c1388c2757f3fa7aab54d012f2e54a9b0f6287f4badb1904194`.
Принят через PR #17: PR CI `30575326764`, post-merge main CI `30575425467`;
main SHA `322cb9ce08f14c017dbdc3bf16c5b91b33238e63`. Полный real+slow suite:
**569 passed in 92.84s**.

## Блок 18: финальная интеграция, локальный RAG и web-панель

### Быстрый запуск панели

Откройте файл в корне проекта, соответствующий вашей системе:

- Windows — `start-admin.cmd`;
- macOS — `start-admin.command`;
- Linux — `start-admin.sh`.

Лаунчер сам перейдёт в папку проекта, проверит наличие `uv`, выполнит
`uv sync --extra rag` и запустит панель. Если `uv` ещё не установлен, откройте
инструкцию: <https://docs.astral.sh/uv/getting-started/installation/>.

Универсальный запуск из терминала в папке проекта:

```bash
uv sync --extra rag
uv run report-processor admin
```

RAG использует `cointegrated/rubert-tiny2`, revision
`e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae` (29.4M параметров, 312 dimensions,
Russian), lazy local load, normalized cosine retrieval и deterministic top-k.
Unavailable dependency/model обрабатывается контролируемо и не изменяет
matching молча. Block 12 authority остаётся primary; semantic-only relations
требуют явного manual review и никогда не принимаются автоматически.

Для локального запуска с самой маленькой проверенной моделью:

```bash
uv sync --extra rag
uv run hf download cointegrated/rubert-tiny2 \
  --revision e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae
uv run report-processor admin
```

Панель открывается на loopback-адресе, принимает от 1 до 32 исходных книг и
один целевой Excel, использует этап `13.1` по умолчанию, показывает расхождения
цветом и требует прямого решения «подходит / не подходит» для неуверенных
RAG-подсказок.
Основной цвет интерфейса — `#0079C2`; он не меняет оформление Excel-отчёта.

Локальный release-gate: **603 passed in 119.80s** с real XLSX, pinned model и
slow/performance. Отдельно: реальная admin-обработка — **1 passed in 4.49s**;
browser desktop/mobile — PASS, console/page/external-request errors — **0**;
base и `[rag]` clean installs, wheel assets, Ruff, format, compileall,
JS syntax и `git diff --check` — PASS. SHA-256 обеих реальных книг не изменились.
Принят через PR #18: PR CI `30580440694`, post-merge main CI `30580539301`;
main SHA `d54fcce5a71c85a1812a3b9209a815499c216e9a`.

### Отдельная функция «Составление отчёта»

В верхнем меню панели выберите **«Составление отчёта»** или откройте
`http://127.0.0.1:8765/drawing-card`. Доступны две прямые операции:

- **Создать новую** — загрузить от 1 до 32 источников `.xlsx`, `.xlsm` или
  `.xlsb`; встроенный шаблон добавляется автоматически.
- **Обновить существующую** — загрузить те же источники и одну готовую карточку
  `.xlsx`.

Панель объединяет периоды из имён и содержимого выбранных книг, по умолчанию
выбирает самый поздний и показывает его как русский месяц и цифровой год.
Если автоматической уверенности недостаточно, спорные строки проверяются прямо
в панели: доступны общие и построчные решения, смена категории, режим
«учитывать только стоимость» и отмена. Явные решения сохраняются локально и
используются в следующих запусках. Файловый `manual_review.xlsx` сохранён как
совместимый запасной путь. Готовый результат скачивается как
`drawing-card.xlsx`. ZIP, каталоги, неверные сигнатуры Excel, небезопасные имена
и превышение лимита отклоняются.

Файлы обрабатываются только в приватном локальном workspace. В JSON и заголовки
не попадают серверные пути. Для подсказки категории используется только
локальная `cointegrated/rubert-tiny2`; сеть во время обработки не требуется,
а семантическая подсказка никогда не подтверждается автоматически. Исходное
проверенное имя сохраняется только у приватной копии, поскольку код объекта
может быть частью имени. Оригиналы остаются неизменными.

Первые столбцы итоговой карточки:
`Шифр чертежа`, `Наименование этапа работ`, `Ед. изм.`, `Количество`,
`Общая стоимость`. Целые количества записываются форматом `0`, дробные —
`0.###`, стоимость — `#,##0.00`.

Текущий bulk acceptance: full real+slow+RAG **647 passed, 3 skipped in
101.12s**. Реальный browser smoke с XLSX и XLSB: HTTP **201**, **38 643**
извлечённые строки, **7 048** строк карточки, **960** строк встроенной проверки;
первый экран показывает 50 решений с русским контекстом и действиями,
console/page errors — **0**. Период по умолчанию — **июль 2026**, ложные будущие
даты не выбираются. Desktop/mobile browser, Ruff, format, compileall, JS syntax
и diff-check — PASS; SHA-256, размер и mtime трёх реальных книг не изменились.

## Блок 15.1: numeric-only XLSX output

Блок 15.1 реализует `ExcelWriterContract-15.1` / `ExcelWriterEngine-15.1` и
`write_target_report(...)`. Запись разрешена только для `ALLOW_WRITE` или
`ALLOW_WRITE_WITH_WARNINGS`; ручная проверка и блокировка возвращают
`SKIPPED_DECISION` без output. Разрешены только `CURRENT_PERIOD_QUANTITY` и
`CURRENT_PERIOD_COST`. Используются конечные `Decimal` без float, пересчёта,
округления или quantize; `None` не очищает ячейку.

Финальный XLSX содержит только числовые значения: worksheet formulas в output
нет. Формулы остаются в неизменяемом source и внутреннем provenance. Если они
есть, LibreOffice headless пересчитывает приватную временную копию с
изолированным профилем; при нулевом числе формул этот шаг пропускается.
Недоступность, timeout, ошибка, blank, text или non-finite результат отменяют
публикацию. Исходник не изменяется; output публикуется атомарно через
hard-link no-clobber и не перезаписывается. CLI в блоке 15.1 нет.

Локальный Block 15.1 gate подтверждён: real-data suite — **7 passed in
44.38s**; полный suite с real XLSX и slow performance — **514 passed in
80.22s**. Ruff, format, clean sync, compileall и `git diff --check` — PASS.
Реальный output: `D30 = 0`, формулы **14 → 0**, merged ranges — **128**;
SHA-256, size и `mtime` исходных книг не изменились. READY/main/CI фиксируются
только после зелёного Pull Request.

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

## Блок 16: audit journal и проверяемые экспорты

Block 16 добавляет контракты `AuditIdentity-16.0`, `AuditEventEnvelope-16.0`,
`StageJournal-16.0`, `AuditBundle-16.0`, `RunReport-16.0`, `TraceReport-16.0`
и `FeedbackRuleVersion-16.0`. SQLite-журнал хранит append-only hash chain с
переходами `PENDING → DATA_COMMITTED → EXPORT_PREPARED → EXPORT_VERIFIED`;
изменение или удаление событий запрещено. Run, report и trace IDs детерминированы,
а экспортные поля redacted и allowlisted.

JSON/JSONL/CSV snapshots сортируются канонически, проверяются по count и SHA-256,
публикуются через fsync и atomic hard-link no-clobber. Ошибочные временные
outputs удаляются; существующий destination не заменяется. Cross-store recovery
сверяет data/export hashes и state. Feedback активируется только после
`EXPORT_VERIFIED`; compaction не переписывает events и сохраняет active versions.

Локальный focused+slow+real gate: **33 passed**; полный real+slow suite —
**547 passed in 89.32s**; 100k — **583.3 B/event**,
append p95 **0.072 ms**. Реальные файлы не изменились. Block 15 принят: PR #15,
CI `30569460356`, main CI `30569606304`, 514 passed и real 7 passed. Block 16
принят через PR #16: PR CI `30572493480`, post-merge main CI `30572598426`,
main SHA `ca6300471b52ba1ef80585b3881cb77e04a6be50`.
