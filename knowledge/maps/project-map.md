---
type: map
tags:
  - knowledge/map
  - domain/document-processing
  - capability/admin-panel
last_verified: 2026-08-01
updated: 2026-08-01
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

## Компоненты и целевые проверки

| Компонент | Ответственность | Целевая проверка |
| --- | --- | --- |
| Сверка документов | `index.html`, `admin.css`, `admin.js`: загрузка, статусы и тема на `/`. | `test_block18_admin_panel.py` + визуальная/file smoke на `/`. |
| Карточка остатков | `drawing-card.html`, `drawing-card.css`, `drawing-card.js`, `drawing-card-review.js`: загрузка, период и inline review. | `test_drawing_card_ui_contract.py`, `test_drawing_card_admin.py` + визуальная/file smoke на `/drawing-card`. |
| Admin API и сервис | `admin_panel/app.py`, `service.py`, `drawing_card_service.py`: локальные HTTP-контракты и изолированные задания. | `test_block18_admin_panel.py`, `test_drawing_card_admin.py`, unit-тесты `admin_panel/`. |
| Сопоставление и feedback | `drawing_card/matching/`, `drawing_card/review/`, `drawing_card/autopilot/`: подбор категории и приоритет явных решений. | `tests/unit/drawing_card/test_*matcher*`, `test_inline_review_flow.py`, `test_block16_feedback.py`. |
| XLSX-результат | `drawing_card/output/`: шаблон, раскладка, форматы и сводка. | `test_drawing_card_service_contract.py`, `test_summary_report.py`, `test_xlsx_xml_precision.py`. |

Политика проверки: локальное уточнение проверяется целевыми component-тестами и
визуальной/file smoke; полный suite запускается только для сквозного изменения,
релиза или явного запроса пользователя.

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
  и содержимого ячеек. Последнее решение по нормализованному наименованию и
  единице заменяет старое, имеет приоритет над встроенным примером и применяется
  до RAG.
- Первые столбцы результата: `Шифр чертежа`, `Наименование этапа работ`,
  `Ед. изм.`, `Количество`, `Общая стоимость, млн руб.`.
- Форматы: все количества `0.00`, стоимость в миллионах рублей `#,##0.00`;
  форматы меняют только отображение, внутренние расчеты остаются в рублях.
- Основной лист XLSX называется `Карточка остатков`. Лист `Сводный отчет`
  показывает по две зеленые карточки индексов в строке и отдельную карточку
  `Все индексы`; каждая содержит восемь категорий и только готовые числовые
  значения без Excel-формул. Количество суммируется только при совместимости
  непустых единиц измерения.
- Незанятые правые секции шаблона удаляются, поэтому пустой четвертый макет не
  отображается при трех индексах.
- Обе страницы имеют прямой переключатель светлой/темной темы и используют
  общий сохраненный выбор `report-processor.theme.v1`; прежний выбор карточки
  подхватывается без сброса. В группе
  проверки используется один компактный блок: категория, режим учета,
  `Применить` и `Отклонить`; отдельные дублирующие кнопки смены категории
  запрещены. При нехватке ширины действия переходят на второй ряд без overflow.

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

## Проверка сводного XLSX и UI

- Task: [[../tasks/drawing-card-summary-review|Сводный XLSX и UI review]].
- Реальный артефакт: 3 индекса, 972 чертежа и четыре карточки 2×2; сводка
  содержит готовые числа, денежные значения — в миллионах рублей.
- Browser evidence: desktop/mobile, light/dark, без console errors и
  горизонтального overflow.
- Финальный gate: `752 passed, 22 skipped`; Ruff, Node syntax и diff-check — OK.

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
