# BUSINESS_RULES — канонический доменный контракт v1

## 1. Термины, входы и неизменяемость

- **Таблица 1** — исходные XLSX КС-2/КС-3/КС-6а. Из них выбираются строки работ, единицы, количество и стоимость за весь период. В обследованном образце единица находится в J, но production-поиск определяет её по смыслу заголовка. Конкретный лист КС-6а и семантический диапазон «за весь период» определяются preflight, а не буквой Excel.
- **Таблица 2** — `Расчет доп отчета карточка 23 Хандюк.xlsx`, лист **`Лист1`**. Это допотчёт: B содержит индекс блока, E — наименование, F — единицу, J — документальное количество, K — млн RUB с НДС, L/M — текущий период.
- Входные файлы не меняются. Их SHA-256, лист, строка и исходный текст каждой выбранной/исключённой строки входят в lineage. Уникальная строка источника: `(source_hash, sheet, row)`.

Наблюдавшиеся Table-1 J/CF/CG (1006), BL/BM (1004), CJ/CK (0919), Table-2 E/F/J/K/L/M и иной лист KITSO — только fixtures. Любой столбец может сдвинуться вправо или остаться на месте. Production-код ищет поля по семантике merged-header tree и не фиксирует буквы колонок.

## 2. Детерминированный выбор файла Таблицы 1

Для каждой непустой ячейки Table 2 `B`:

1. Нормализовать текст и имя файла Unicode NFKC, trim и case-fold; не заменять кириллическую `а` на латинскую `a` и наоборот.
2. Взять **суффикс после последней точки** в `B` как index; сохранить ведущие нули. Пустой суффикс — ошибка preflight.
3. Отбросить файлы, начинающиеся с `~$`.
4. Принять имя только если оно содержит index как отдельный токен: с обеих сторон начало/конец имени либо символ, не являющийся буквой/цифрой Unicode. Подстрока внутри большего номера не подходит.
5. Имя должно также содержать отдельный токен `6а`: допустимы кириллическая `а`, латинская `a` и любой регистр (`6а`, `6А`, `6a`, `6A`). Другие части имени не обязаны иметь фиксированные буквы или шаблон.
6. Semantic preflight извлекает stage из содержимого каждого workbook и сравнивает его с явно указанным stage UI/CLI (UI initially `13.1`; batch/CLI has no hidden default). Missing, mismatch или несколько semantic stage values — blocker. Имя файла только сужает список и никогда не доказывает stage. Версия определяется только явным правилом владельца или ручным выбором.

`0` кандидатов — blocker с причиной и ручным выбором/явным пропуском. `>1` — blocker с перечнем hash, имени, даты/версии и действием «Выбрать кандидата»; первый по имени/дате никогда не выбирается молча. Тесты включают leading zero, boundary, `6а`/`6a`/регистр, `~$`, stage extracted from content, missing/mismatch/ambiguous stage, misleading filename, conflicting content и schema-version случаи.

## 3. Нормализация и приоритет

Текст нормализуется NFKC, trim и схлопыванием пробелов; comparison keys case-fold. Правило имеет `rule_id`, `rule_version`, Table-2 key, literal Table-1 include/exclude, suffix semantics, stage/scope, `unit_policy`, `priority`, `status`, `evidence` и `owner_approval`.

Приоритет: hard exclude → точное подтверждённое правило → literal include → candidate-only → fuzzy/GPT candidate. Более широкое правило не отменяет более узкое; равный приоритет с несовместимым результатом — collision blocker. Ни fuzzy, ни GPT не создают автоматическое совпадение.

Если после нормализации и применения mapping для процесса Table 2 в Table 1 нет ни одной строки-кандидата по наименованию, результат количества и стоимости равен `0`; это состояние `no_process_match`, а не unit mismatch. Если кандидаты есть, система предварительно отмечает рекомендуемые строки как `include=true`, но сомнительный выбор требует подтверждения пользователя на review-экране.

## 4. Четырнадцать пользовательских соответствий (versioned mappings v1)

Repeated spaces/typos are normalized under §3, but every mapping remains a separate versioned ID and preserves the literal shown below. `+ suffix` means the Table 2 key's value/suffix must match under the owner-approved suffix semantics; otherwise the row is candidate-only.

| ID | Table 2 literal | Table 1 literal include | Exclude / suffix / result |
| --- | --- | --- | --- |
| M01 | «Устройство свайных фундаментов» | «Устройство основания из буроопускных металлических свай» | Exclude any pile tests. |
| M02 | «Бетонные работы» | «Армирование и бетонирование монолитных участков из бетона (участки из жаростойкого бетона)»; «Армирование и бетонирование монолитных участков из бетона»; «Бетонирование фундаментов»; «Бетонирование фундаментов общего назначения» | Exclude «железобетон». |
| M03 | «Монтаж ТТ и СДТ КГС» | «Монтаж ТТ Д» + suffix | Монтаж трубопровода/похожие строки only candidate review. |
| M04 | «Прокладка кабеля, провода (Силовые сети) КГС» | No approved literal Table 1 include set: all candidates are candidate-only | Exclude «Разводка по устройствам и подключение жил электрических кабелей»; supporting works candidate-only until owner provides the exact power include set. |
| M05 | «Прокладка кабеля, провода (Слаботочные сети) КГС» | No approved literal Table 1 include set: all candidates are candidate-only | Power/cross-category/unclear rows are candidate-only and never auto-included until owner provides the exact low-current include set. |
| M06 | «Монтаж металлоконструкций» | «Монтаж м/к фундаментов и ростверков»; «Монтаж м/к каркасов зданий и сооружений»; «Монтаж м/к эстакад»; «Монтаж малых конструктивных элементов м/к(монтаж жалюзийных решеток)» | Exclude exact «Монтаж м/к мачт-молниеотводов»; «Монтаж м/к антенных мачт»; «Изготовление м/к (прим. емкостей)». |
| M07 | «Сварка в нитку» | «сварка» + suffix | No matching suffix → candidate-only. |
| M08 | «Укладка трубопроводов (укладка)» | «Укладка трубопроводов» + suffix | No matching suffix → candidate-only. |
| M09 | «Бетонные работы» | «Бетонирование фундаментов»; «Бетонирование фундаментов общего назначения» | Separate and traceable despite overlap with M02; de-duplicate identical source row. |
| M10 | «Обратная засыпка» | «Обратная засыпка траншеи под трубопровод» | No broadening to other backfill. |
| M11 | «Разработка траншеи» | «Разработка траншеи под трубопровод» | No broadening to other excavation. |
| M12 | «Монтаж опор ВЛ» | «Комплект анкерной концевой опоры» + suffix | Never equal to «Монтаж железобетонных опор ВЛ» when the latter is measured in tonnes. |
| M13 | «Монтаж силового кабеля ВЛ» | «Прокладка самонесущего кабеля ВОЛС по стальным опорам» | Suspicious/candidate-only and collision blocker with M14. |
| M14 | «Монтаж ВОЛС ВЛ» | «Прокладка самонесущего кабеля ВОЛС по стальным опорам» | Collision blocker with M13; no automatic application. |

## 5. Расчёт, деньги и статусы

- Количество и стоимость берутся из Table 1 за **весь период** через semantic headers. Единица Table 2 (в образце F) сравнивается с единицей каждой строки Table 1 (в образце J). Буквы F/J — fixtures, а не контракт координат.
- Для проверки единиц применяются NFKC, trim, схлопывание пробелов и case-fold, но не автоматическая конверсия. Физическое количество сначала суммируется по одобренным строкам с единицей Table 2. Если таких строк нет и у всех одобренных кандидатов одна общая альтернативная единица, их количество суммируется в этой единице, а ячейка единицы Table 2 становится красной и получает `исходная_единица/единица_Table1`. Если альтернативных единиц несколько, система показывает отдельный subtotal для каждой единицы; они никогда не складываются между собой, а пользователь выбирает одну unit-group прямым переключателем.
- Все суммы/количества — `Decimal`; суммируются сырые RUB по строкам, и только затем результат один раз делится на `1_000_000` для вывода в млн RUB. Никаких float, округления по строкам или повторного деления.
- Денежная стоимость суммируется по всем одобренным строкам соответствия независимо от совпадения единиц. Unit mismatch не исключает стоимость, но остаётся видимым предупреждением и сохраняется в lineage.
- Коэффициент `2.7` — средний контрольный ориентир, а не преобразование стоимости и не строгая бухгалтерская проверка. После расчёта основной стоимости выполняется отдельная проверка `control_cost = (Table1_raw_cost_RUB / 1_000_000) × 2.7`. Если `control_cost >= Table2.K`, статус `cost_check_ok`; если меньше — `cost_check_warning`, который подсвечивается пользователю как повод проверить состав строк. Сама заносимая стоимость остаётся суммой Table 1, делённой на `1_000_000`, без умножения на `2.7`.
- Для warning сохраняются и показываются: исходная сумма Table 1 в млн RUB, coefficient, `control_cost`, Table2.K, абсолютная разница и lineage включённых строк. Проверка использует `Decimal` без промежуточного округления.
- UI показывает одно поле коэффициента на весь run со значением по умолчанию `2.7`; per-row коэффициентов нет. Изменение поля сразу пересчитывает все control statuses. `cost_check_warning` выделяется оранжевым, не блокирует export после отдельного явного acknowledgement пользователя. Значение коэффициента, warning evidence, actor/time acknowledgement и комментарий входят в manifest/audit.
- `Table2.J` и `Table2.L` сравниваются как числовые `Decimal`, не как текст. Оба значения округляются до двух знаков только для этого сравнения; после округления точное равенство подсвечивается жёлтым без дополнительного tolerance. Форматы `1`, `1.0`, `1.000` равны; `0 = 0` также жёлтый. Поведение двух пустых ячеек и rounding mode остаются Gate 0; пустое значение никогда автоматически не превращается в числовой ноль.
- Unit mismatch остаётся красным и содержит old/source. При единственной альтернативной единице количество суммируется в ней; при нескольких единицах используются раздельные subtotals и явный выбор одной группы. Стоимость всех одобренных строк включается независимо от выбранной quantity group. Отсутствие любого совпадения по наименованию даёт `0/0` и не подменяется unit mismatch. Автоматическая конверсия между единицами остаётся Gate-0 blocker. Duplicate lineage, stale formula/freshness failure, malformed Decimal, missing/multiple candidate, ambiguous match и M13/M14 collision — blockers.

## 6. Feedback memory, а не online training

Каждая строка-кандидат Table 1 показывается с наименованием, единицей, количеством, стоимостью, source file/sheet/row, причиной и уверенностью. Прямой checkbox **«Учитывать»** отражает `include=true/false`: рекомендуемые строки предварительно отмечены, сомнительные выделены и требуют подтверждения. Пользователь может снять/поставить галочку и добавить необязательный комментарий; итог пересчитывается детерминированно до экспорта.

Подтверждение inclusion/exclusion/выбора кандидата сохраняется как решение текущего run. Только отдельное явное действие **«Запомнить правило»** может создать versioned feedback rule; снятая галочка с комментарием лишь предлагает exclusion-кандидат и не создаёт reusable rule сама.

Минимальный ключ памяти: Table-2 category, normalized Table-1 item, stage/scope, units и baseline rule version. Active data компактны: canonical normalized entities в SQLite имеют integer IDs/FKs и hashes; каждая unique raw string хранится один раз/deduplicated; decision events ссылаются на IDs, а не копируют prose. Active rule records не содержат длинных raw text/prompts; append-only audit отделён от materialized active snapshot. Payload: rule id/version/status, include/exclude/candidate value, user, timestamp, source hash, comment, prior/new value и provenance. Перед reuse проверяются все ключи и schema/rule version compatibility. Несовместимый контекст, conflict, schema drift или duplicate rule — review blocker; правило не расширяется с одного item до всей категории и не применяется молча.

Есть undo текущего решения, deactivate feedback rule и rollback к прежней версии с audit trail. Deterministic retrieval сначала выполняется SQL с indexes по category/stage/unit/status/version; archived events исключены из AI prompt. Compaction/retention может архивировать inactive events и deduplicate raw strings, но никогда не удаляет financial lineage/audit; результат до/после compaction идентичен. Тесты обязаны доказывать reuse только в совместимом контексте, context isolation, conflict, rollback, schema drift, duplicate prevention, collision M13/M14, zero duplicate raw strings, storage growth per decision и retrieval latency на large corpus.

## 7. Gate 0 — решения владельца

До owner-approved записи запрещены scaffold и реализация. Владелец обязан решить: M04 exact power include set, M05 exact low-current include set, M13/M14; stage и version-selection policy; лист/whole-period semantics; quantity destination/new-column meaning; J/L blank behavior и two-decimal rounding mode; automatic unit conversion policy; formula freshness/recalc policy; M03/M07/M08/M12 suffix semantics и M04 supporting works; output precision outside J/L comparison/overwrite; feedback reuse, compatible context и retention/rollback policy; configurable AI context/token budget. Numeric J/L comparison after two-decimal rounding, coefficient flow, `0/0`, checkbox review и alternative-unit behavior уже утверждены. M02/M06 four literal variants already approved and are not reopened. Thresholds storage growth, retrieval latency и prompt tokens owner-approved, не implementation defaults.

## 8. Проверяемые инварианты

Результат order-independent; каждое значение имеет lineage; export запрещён при любом unresolved blocker; rules и feedback versioned; original hash неизменён. Goldens 1006: сваи `261 / 37.313343`, бетон `2.36 / 0.034239`, ТТ `2138.059 / 33.75002661`, металлоконструкции `100.39863 / 12.59387023` (количество / млн RUB).
