# Document Optimizer

Python-проект для поэтапной обработки строительных отчётов КС-2, КС-3, КС-6а,
СВВР, допотчётов и связанных документов.

## Текущий статус

Интегрированы **блоки 1–3 — «Каркас проекта, инвентаризация источников,
индексы документов и детерминированный выбор источника»**.
Проект принимает каталог, отдельный файл или ZIP-архив и строит типизированный
JSON-манифест без чтения содержимого Excel и без распаковки ZIP. Блок 2
обогащает готовый `FileManifest` индексами вида `1006 (682)` по имени и
относительному пути; повторное сканирование источника не требуется.

Состояние следующих блоков не реализовано заранее. Подробности приведены в
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

## Ограничения блоков 1–3

Намеренно не реализованы:

- открытие Excel-книг;
- чтение листов и ячеек;
- сопоставление документов и работ;
- расчёты количества и стоимости;
- DuckDB, Parquet, pandas и openpyxl;
- изменение или полная распаковка исходных файлов;
- код следующих блоков.

Архивные даты ZIP не содержат часовой пояс по формату ZIP, поэтому сохраняются
как локальные наивные значения. Полный хеш содержимого больших файлов не
вычисляется: `file_id` является техническим идентификатором метаданных.

Индекс извлекается только из имени и относительного пути, без открытия Excel.
Шаблон по умолчанию строгий: `main (secondary)`, а неоднозначные, похожие на год
и loose-кандидаты не выдаются как подтверждённый индекс.

## Архитектура

Модули и границы ответственности описаны в
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
