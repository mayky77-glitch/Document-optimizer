---
type: decisions
tags:
  - knowledge/decision
last_verified: 2026-08-13
updated: 2026-08-13
---

# Decisions

Record only accepted cross-cutting decisions. Link each decision to affected component cards and tasks; do not duplicate implementation detail here.

## DO-010: бизнес-правила остаются данными

Блок 10 принимает JSON и YAML, но после строгой валидации строит
одинаковые immutable models и canonical JSON bytes. YAML tags, anchors, aliases,
includes, environment interpolation и любые executable constructs запрещены.
Связанные карточки: [[tasks/document-optimizer-block-10-production]],
[[tasks/document-optimizer-blocks-09-10-tests]].

## DO-011: сводный XLSX публикует готовые числовые значения

`Сводный отчет` хранит только готовые числовые значения для восьми категорий
по каждому индексу и для `Все индексы`; формулы в пользовательский файл не
попадают. Индексы отображаются карточками по две в строке, а общий итог —
отдельной карточкой. Основной лист называется `Карточка остатков`. Внутренняя
математика остается в рублях, но все денежные ячейки отчета публикуются в
миллионах рублей. Все количества и стоимости отображаются ровно с двумя
знаками после запятой, без округления сохраненного числового значения.
Стоимость суммируется независимо от единицы.
Количество суммируется только если каждый индекс имеет одну и ту же непустую
нормализованную единицу; пропуск или смешение блокирует публикацию вместо
тихой потери данных. Незанятые правые секции шаблона удаляются.
Связанные карточки: [[tasks/drawing-card-summary-production]],
[[tasks/drawing-card-summary-tests]], [[tasks/drawing-card-summary-review]].

## DO-012: тема и решение по группе управляются напрямую

Светлая/темная тема переключается одной кнопкой и хранится только локально в
браузере. Нерешенная группа имеет единый поток: категория, двухпозиционный
режим учета, `Применить` или `Отклонить`. Смена категории не создает второй
набор кнопок подтверждения. Длинные подписи переносятся внутри сегмента; при
нехватке ширины действия переходят на второй ряд без горизонтального overflow.
Связанные карточки: [[tasks/drawing-card-summary-ui]],
[[tasks/drawing-card-summary-review]].

Карточная XLSX-сводка и компактный UI закреплены задачами
[[tasks/summary-layout-xlsx]], [[tasks/summary-layout-ui]] и
[[tasks/summary-layout-tests]].

## DO-013: последнее явное review-решение является правилом

Подтверждение, смена категории, режим `только стоимость`, отклонение и пропуск
сохраняются в приватном feedback store по нормализованному наименованию и
единице. Новое явное решение заменяет старое и имеет приоритет над встроенным
примером с тем же ключом. Такое правило применяется до RAG, поэтому идентичная
строка повторно не требует ручной карточки. Пути, имена файлов и исходные
пользовательские наименования не копируются в project knowledge.
Связанные карточки: [[tasks/feedback-rule-reuse]],
[[tasks/million-feedback-tests]].

## DO-014: договорные значения и feedback публикуются детерминированно (2026-08-03)

Итоги договора и выполненного периода используют соответствующие source row sets,
Decimal/рубли внутри и миллионы только при публикации; превышение проверяется строго
выше 1 000 руб., красной остаётся только contract-cost. Перед rerun сохраняется RAG
snapshot, а replay выполняется только по точному normalized name + normalized unit;
другая единица требует ручной проверки. Основание: принятая реализация и focused
регрессия 2026-08-03.
Связанные карточки: [[components/drawing-card]],
[[tasks/drawing-card-contract-check-rag-plan]].

## DO-015: claims проверки и сверки разделяются (2026-08-13)

Пользовательская «Проверка документов» (`operation=verify`) и соседняя авторитетная сверка с
записью target J/K (`operation=reconcile`) считаются разными контрактами. Выводы о корректной
Decimal-арифметике или verified target output режима `reconcile` не доказывают точность verdict
или красной разметки `verify`. Текущий `verify` нельзя описывать как числовое сравнение либо как
100%-точную проверку: числового oracle нет, а реальные ingestion/writer/stage дефекты открыты.

Эта запись не выбирает будущую бизнес-семантику. Определение числового равенства и способ выбора
этапа остаются owner-gates до новой реализации. Связанные карточки:
[[components/document-verification]], [[tasks/reconciliation-max-accuracy-audit-v1]],
[[errors/reconciliation-accuracy-findings]],
[[tasks/admin-verification-accuracy-remediation]].

## DO-016: PropExtract используется только как источник методик (2026-08-13)

Публичный проект PropExtract можно использовать при анализе `operation=verify` как внешний
сравнительный источник методик: exact-or-ambiguous identity, field-level provenance,
order-independent consensus, narrow normalization, staged workbook validation и adversarial
permutation tests. Его предметные RNS/PDF/OCR-правила не переносятся автоматически.

На проверенном commit отсутствует верхнеуровневая лицензия приложения, поэтому код, тесты и
fixtures не копируются. Любое code reuse требует отдельного разрешения правообладателя/лицензии;
новая реализация должна быть независимой. Связанная карточка:
[[research/propextract-methods-2026-08-13]],
[[tasks/admin-verification-accuracy-remediation]].
