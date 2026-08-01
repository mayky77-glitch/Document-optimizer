---
type: decisions
tags:
  - knowledge/decision
last_verified: 2026-08-01
updated: 2026-08-01
---

# Decisions

Record only accepted cross-cutting decisions. Link each decision to affected component cards and tasks; do not duplicate implementation detail here.

## DO-010: бизнес-правила остаются данными

Блок 10 принимает JSON и YAML, но после строгой валидации строит
одинаковые immutable models и canonical JSON bytes. YAML tags, anchors, aliases,
includes, environment interpolation и любые executable constructs запрещены.
Связанные карточки: [[tasks/document-optimizer-block-10-production]],
[[tasks/document-optimizer-blocks-09-10-tests]].

## DO-011: сводный XLSX остается формульным и консервативным по единицам

`Сводный отчет` хранит Excel `SUMIF`-формулы для восьми категорий по каждому
индексу и для `Все индексы`. Индексы отображаются карточками по две в строке,
а общий итог — отдельной карточкой. Основной лист называется
`Карточка остатков`. Стоимость суммируется независимо от единицы.
Количество суммируется только если каждый индекс имеет одну и ту же непустую
нормализованную единицу; пропуск или смешение блокирует публикацию вместо
тихой потери данных. Незанятые правые секции шаблона удаляются.
Связанные карточки: [[tasks/drawing-card-summary-production]],
[[tasks/drawing-card-summary-tests]], [[tasks/drawing-card-summary-review]].

## DO-012: тема и решение по группе управляются напрямую

Светлая/темная тема переключается одной кнопкой и хранится только локально в
браузере. Нерешенная группа имеет единый поток: категория, двухпозиционный
режим учета, `Применить` или `Отклонить`. Смена категории не создает второй
набор кнопок подтверждения. Desktop-ряд ограничен по ширине и не растягивает
контролы; на узком экране он безопасно переносится.
Связанные карточки: [[tasks/drawing-card-summary-ui]],
[[tasks/drawing-card-summary-review]].

Карточная XLSX-сводка и компактный UI закреплены задачами
[[tasks/summary-layout-xlsx]], [[tasks/summary-layout-ui]] и
[[tasks/summary-layout-tests]].
