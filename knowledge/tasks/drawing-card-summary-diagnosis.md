---
type: task
status: done
work_id: drawing-card-summary-v1
role: worker
agent_role: debugger
owner: "summary-debugger"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: "summary-contract-validated-2026-08-01"
no_progress_count: 0
circuit_state: closed
routing_reason: "\u0424\u0438\u043d\u0430\u043d\u0441\u043e\u0432\u044b\u0439 XLSX: \u043d\u0443\u0436\u0435\u043d \u0442\u043e\u0447\u043d\u044b\u0439 \u043a\u043e\u043d\u0442\u0440\u0430\u043a\u0442 ghost-slot, \u0444\u043e\u0440\u043c\u0443\u043b \u0438 recalc"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: "Persistent debugger profile; runtime did not expose an independent launch confirmation."
model_fallback: false
last_verified: 2026-08-01
updated: 2026-08-01
write_scope:
  - knowledge/tasks/drawing-card-summary-diagnosis.md
source_paths:
  - src/report_processor/drawing_card/models.py
  - src/report_processor/drawing_card/output/layout.py
  - src/report_processor/drawing_card/output/writer.py
  - src/report_processor/drawing_card/output/validator.py
  - src/report_processor/drawing_card/output/xlsx_xml.py
  - src/report_processor/excel_writer/formula_materialization.py
  - tests/fixtures/drawing_card/default_template.xlsx
  - output/Карточка чертежей 2026-07.xlsx
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
  - "drawing-card"
  - "xlsx"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Диагностика пустого XLSX-блока и формул сводки

## Goal

Передать developer точный контракт сводки и устранения пустого template-slot.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Evidence

- `PYTHONPATH=src python3 ... validate_card(output/Карточка чертежей 2026-07.xlsx)` вернул `OK`: 1 лист, 3 индекса (`0906`, `0907`, `0908`), 972 чертежа, ошибок нет.
- В текущем output нет worksheet formulas, `xl/workbook.xml` не содержит `calcPr`; следовательно Excel не получает ни формул сводки, ни явного запроса пересчёта.
- `TargetWorkCategory` / `CATEGORY_ORDER` определяют ровно 8 категорий в стабильном порядке (`models.py:12-35`). Каждый блок чертежа уже занимает 8 строк (`layout.py:35-41`).
- Шаблон и bundled resource идентичны (SHA-256 `cea026...f5ed98`), имеют 4 стилизованных слота `B:F`, `H:L`, `N:R`, `T:X` и 4 merge-range (`E2:F2`, `K2:L2`, `Q2:R2`, `W2:X2`).
- `plan_layout(..., objects_per_sheet=4)` размещает только первые 3 реальных индекса в output; `_clear_template_values` очищает значения всех 4 слотов, но намеренно сохраняет styles, dimensions и merges (`writer.py:176-186`). Поэтому незанятый `T:X` остаётся визуально как пустая карточка; это воспроизводится в реальном output (styles `T4:X4` присутствуют, header `T2` пуст).
- `validator.py` валидирует карточки, категории, числовые форматы и архив, но не требует сводный лист, формулы или calculation properties (`validator.py:177-238`). Прямых тестов `write_card`/`validate_card` для drawing-card output нет.
- У существующего `excel_writer.formula_materialization.recalculate_and_materialize` обратный контракт: после LibreOffice он заменяет формулы числами (`formula_materialization.py:23-46`). Его нельзя вызывать для требуемой пользователю Excel-сводки.
- В реальном output unit в пределах каждой пары индекс/категория согласован. Это не гарантирует будущие запуски: текущая агрегация защищает unit mismatch лишь внутри одного чертежа (`aggregation/aggregator.py:99-105`), поэтому all-index quantity нельзя молча суммировать при разных единицах.

## Proposed output contract

1. Добавить отдельный лист `Сводный отчет` без изменения данных карточек. Таблица имеет колонки `Индекс объекта`, `Наименование этапа работ`, `Ед. изм.`, `Количество`, `Общая стоимость`; порядок категорий ровно `CATEGORY_ORDER`.
2. Для каждого `ObjectBlockLayout` создать ровно 8 строк: индекс + соответствующая category display name + unit. Количество и стоимость — Excel-formulas `SUMIF` по category/metric columns именно этого layout от `data_start_row` до последнего `DrawingCodeBlockLayout.end_row`; формула ссылается на category-cell summary row, а не дублирует русский текст. Так в 2026-07 получится 24 index rows.
3. После index rows добавить ровно 8 строк `Все индексы`. Их quantity/cost formulas используют `SUMIF` только по диапазону index summary rows, исключая собственную total section. Это ограничивает длину формулы при любом количестве индексов и не требует 3D/volatile formulas.
4. Unit в all-index row допускается только если все index rows данной category имеют один нормализованный non-empty unit; иначе не писать quantity-formula, оставить quantity empty и сделать publication validation error `SUMMARY_MIXED_UNIT:<category>`. Стоимость суммируется независимо от unit.
5. Formula text должен быть OOXML/Excel invariant English (`=SUMIF(...)`, comma separator; без локализованных русских function names). Не использовать `SUMIFS`/structured references/volatile `INDIRECT`; openpyxl сохраняет formula, но не рассчитывает cache.
6. Для workbook выставить `calcMode=auto`, `fullCalcOnLoad=1`, `forceFullCalc=1`; удалить calcChain, если он есть. В релизной проверке открыть private copy LibreOffice headless, сравнить numeric cached results с ожидаемыми Decimal totals и убедиться, что published `Сводка` всё ещё содержит `<f>` formulas. Нельзя применять existing materializer, поскольку он удаляет formulas.
7. На последнем листе после размещения удалить только правые неприменённые template-slots: сначала unmerge merge этого slot, затем delete его пять data columns. Никогда не удалять slot, присутствующий в `layouts`, и не удалять separator/occupied slots. `objects_per_sheet=4` и template capacity остаются без изменения.
8. Расширить validator: required `Сводный отчет`; exact 8 × (number of layouts + 1) rows; category order; formula coordinates and expected `SUMIF` dependencies/ranges; unit condition; `calcPr` flags; no formula errors after recalculation; no styled vacant trailing slot. Existing card validation remains unchanged for card data and exact numeric XML.

## Risks

- Формулы, записанные openpyxl, имеют no cached result до Excel/LibreOffice. `data_only=True` не является доказательством результата до recalculation.
- LibreOffice может переписать OOXML/styling; проверять private recalculated copy, а published workbook проверять статически на formulas + `calcPr` и по результатам private copy.
- Если update mode получает пользовательский лист с именем `Сводка`, нужна явно выбранная политика: удалить/пересоздать только лист с подтверждённым system marker либо завершиться контролируемой ошибкой, а не затереть пользовательские данные.

## Precise developer handoff

`developer` владеет новым модулем `src/report_processor/drawing_card/output/summary.py` и интеграцией в `writer.py`/`validator.py`: реализовать вышеописанный `Сводный отчет` contract, направить private LibreOffice verification в тестовый helper (не existing formula materializer), и добавить unit/integration tests с 3 occupied из 4 slots, 8 категорий на индекс, 8 all-index rows, `calcPr`, formulas retained, mixed-unit rejection и безопасным trim только `T:X`.

## Proposed knowledge delta

- После принятия реализации обновить component card output: publication теперь содержит formula-bearing `Сводка`, separate recalculation verification и trailing-slot trimming; numeric-only `excel_writer/` остаётся отдельной, несовместимой boundary.

## Handoff

Accepted after implementation and regression verification.
