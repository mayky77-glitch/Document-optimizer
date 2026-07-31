---
type: map
tags:
  - knowledge/map
  - domain/document-processing
  - capability/admin-panel
last_verified: 2026-07-31
updated: 2026-07-31
---

# Карта проекта

Короткая точка входа для следующих задач. Код и тесты остаются источником
истины; открывать только указанный компонент и связанный task card.

## Пользовательские функции

| Функция | URL | Основной код | Проверки |
| --- | --- | --- | --- |
| Сверка документов | `/` | `admin_panel/service.py`, `assets/admin.*` | `tests/unit/admin_panel`, `test_block18_admin_panel.py` |
| Карточка остатков | `/drawing-card` | `admin_panel/drawing_card_*`, `drawing_card/`, `assets/drawing-card.*` | `tests/unit/drawing_card`, `test_drawing_card_admin.py` |
| Поиск периодов | `/api/drawing-card/periods` | `drawing_card/periods.py` | `test_drawing_card_periods.py` |
| Локальный RAG | внутри карточки | `stage_rag/`, `drawing_card/review.py` | `tests/unit/stage_rag`, `test_block18_rag.py` |

## Зафиксированные контракты

- Обе функции принимают 1–32 исходных `.xlsx`, `.xlsm` или `.xlsb`.
- Сверка дополнительно принимает один целевой Excel-файл.
- Периоды объединяются из имён и содержимого книг; по умолчанию выбирается
  самый поздний, подпись — русский месяц и цифровой год.
- RAG: только локальная `cointegrated/rubert-tiny2` с закреплённой revision;
  подсказка не принимается автоматически.
- Проверка спорных строк выполняется внутри панели: общее и построчное решение,
  смена категории, режим «учитывать только стоимость», отмена.
- Явные решения сохраняются в приватном feedback store без путей, имён файлов
  и содержимого ячеек.
- Первые столбцы результата: `Шифр чертежа`, `Наименование этапа работ`,
  `Ед. изм.`, `Количество`, `Общая стоимость`.
- Форматы: целое количество `0`, дробное `0.###`, стоимость `#,##0.00`.

## Безопасность данных

- Оригиналы открываются только для чтения; обработка идёт в приватных временных
  копиях.
- В API не возвращаются локальные пути, имена листов, формулы и исходные
  значения.
- Реальные проверки задаются через `DOCUMENT_OPTIMIZER_*` environment variables;
  приватные пути и имена файлов в vault не записываются.
- Реестр завершённых web-задач ограничен; активная проверка не вытесняется.

## Быстрые проверки

```bash
uv run ruff check src tests
uv run ruff format --check src tests
node --check src/report_processor/admin_panel/assets/admin.js
node --check src/report_processor/admin_panel/assets/drawing-card.js
uv run pytest -q
```

## Связанные задачи

- [[../tasks/bulk-reconciliation-v1-core]]
- [[../tasks/bulk-reconciliation-v1-ui]]
- [[../tasks/bulk-reconciliation-v1-tests]]
- [[../tasks/bulk-reconciliation-v1-design-parity]]

## Последний релиз

- PR: `#24`
- main: `9b8c3e87f81e6aff3ffcd2766657a5274974bdda`
- PR CI: `30603894650` — success
- post-merge main CI: `30603954828` — success
- full real+slow+RAG: `647 passed, 3 skipped in 101.12s`
