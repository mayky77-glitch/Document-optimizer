# BUSINESS_RULES — канонический доменный контракт v1

## 1. Термины, входы и неизменяемость

- **Таблица 1** — исходные XLSX КС-2/КС-3/КС-6а. Из них выбираются строки работ, единицы, количество и стоимость за весь период. В обследованном образце единица находится в J, но production-поиск определяет её по смыслу заголовка. Конкретный лист КС-6а и семантический диапазон «за весь период» определяются preflight, а не буквой Excel.
- **Таблица 2** — `Расчет доп отчета карточка 23 Хандюк.xlsx`, лист **`Лист1`**. Это допотчёт: B содержит индекс блока, E — наименование, F — единицу, J — документальное количество, K — млн RUB с НДС, L/M — текущий период.
- Входные файлы не меняются. Их SHA-256, лист, строка и исходный текст каждой выбранной/исключённой строки входят в lineage. Уникальная строка источника: `(source_hash, sheet, row)`.
- Из Table 1 читаются только сохранённые значения ячеек (`data-only` view). Формулы, ссылки и вычислительная логика Table 1 никогда не копируются в Table 2. Все агрегаты рассчитывает deterministic core.

Наблюдавшиеся Table-1 J/CF/CG (1006), BL/BM (1004), CJ/CK (0919), Table-2 E/F/J/K/L/M и иной лист KITSO — только fixtures. Любой столбец может сдвинуться вправо или остаться на месте. Production-код ищет поля по семантике merged-header tree и не фиксирует буквы колонок.

Preflight Table 1 допускает варианты регистра/алфавита в имени листа `КС-6а`/`KS-6a`, но расчёт читает только этот semantic sheet. В нём выбирается только merged-header block со смыслом **«ВЫПОЛНЕНО ЗА ВЕСЬ ПЕРИОД СТРОИТЕЛЬСТВА»**, включая доказанные орфографические/формулировочные варианты вроде «СТРОИТЕЛЬСВА» и «с начала строительства». Листы КС-2/КС-3 и current-month blocks исключены. Ноль подходящих листов/блоков — blocker; несколько — список evidence и явный выбор пользователя, без автоматического объединения.

## 2. Детерминированный выбор файла Таблицы 1

Для каждой непустой ячейки Table 2 `B`:

1. Нормализовать текст и имя файла Unicode NFKC, trim и case-fold; не заменять кириллическую `а` на латинскую `a` и наоборот.
2. Взять **суффикс после последней точки** в `B` как index; сохранить ведущие нули. Пустой суффикс — ошибка preflight.
3. Отбросить файлы, начинающиеся с `~$`.
4. Принять имя только если оно содержит index как отдельный токен: с обеих сторон начало/конец имени либо символ, не являющийся буквой/цифрой Unicode. Подстрока внутри большего номера не подходит.
5. Имя должно также содержать отдельный токен `6а`: допустимы кириллическая `а`, латинская `a` и любой регистр (`6а`, `6А`, `6a`, `6A`). Другие части имени не обязаны иметь фиксированные буквы или шаблон.
6. Semantic preflight извлекает stage и month/current period из содержимого каждого workbook и сравнивает их с явно указанными UI/CLI значениями (UI stage initially `13.1`; batch/CLI has no hidden default). Filename только сужает кандидатов и никогда не доказывает stage/month.
7. Несколько кандидатов ранжируются строго: semantic stage match → semantic month match → наибольший явный номер `редN` в имени (`ред2 > ред1`; отсутствие номера ниже numbered revision). Modification time не является приоритетом. Если после ранжирования остаётся несколько файлов, система может рекомендовать вариант по schema completeness/data-quality evidence, но не выбирает его автоматически: пользователь видит варианты/evidence и подтверждает один.

`0` кандидатов — blocker с причиной и ручным выбором/явным пропуском. Неразрешённая множественность — blocker до user confirmation. Тесты включают leading zero, boundary, `6а`/`6a`/case, `~$`, semantic stage/month, misleading filename, `ред1/ред2/no-revision`, misleading mtime, schema-quality tie и explicit confirmation.

## 3. Нормализация и приоритет

Текст нормализуется NFKC, trim и схлопыванием пробелов; comparison keys case-fold. Правило имеет `rule_id`, `rule_version`, Table-2 key, literal Table-1 include/exclude, suffix semantics, stage/scope, `unit_policy`, `priority`, `status`, `evidence` и `owner_approval`.

Приоритет: hard exclude → точное подтверждённое правило → literal include → candidate-only → fuzzy/GPT candidate. Более широкое правило не отменяет более узкое; равный приоритет с несовместимым результатом — collision blocker. Ни fuzzy, ни GPT не создают автоматическое совпадение.

Если после нормализации и применения mapping для процесса Table 2 в Table 1 нет ни одной строки-кандидата по наименованию, результат количества и стоимости равен `0`; это состояние `no_process_match`, а не unit mismatch. Если кандидаты есть, система предварительно отмечает рекомендуемые строки как `include=true`, но сомнительный выбор требует подтверждения пользователя на review-экране.

## 4. Четырнадцать пользовательских соответствий (versioned mappings v1)

Repeated spaces/typos are normalized under §3, but every mapping remains a separate versioned ID and preserves the literal shown below. `+ suffix` means a normalized Table-1 string equals the base phrase or starts with that phrase followed by any diameter, mark, number or clarifying text. The continuation is not separately compared with Table 2. A hard exclude still wins.

| ID | Table 2 literal | Table 1 literal include | Exclude / suffix / result |
| --- | --- | --- | --- |
| M01 | «Устройство свайных фундаментов» | «Устройство основания из буроопускных металлических свай» | Exclude any pile tests. |
| M02 | «Бетонные работы» | «Армирование и бетонирование монолитных участков из бетона (участки из жаростойкого бетона)»; «Армирование и бетонирование монолитных участков из бетона»; «Бетонирование фундаментов»; «Бетонирование фундаментов общего назначения» | Exclude «железобетон». |
| M03 | «Монтаж ТТ и СДТ КГС» | «Монтаж ТТ Д» + suffix | Exact/prefix match auto-candidate; монтаж трубопровода/похожие строки only candidate review. |
| M04 | «Прокладка кабеля, провода (Силовые сети) КГС» | No approved literal Table 1 include set: all candidates are candidate-only | Exclude «Разводка по устройствам и подключение жил электрических кабелей»; supporting works candidate-only until owner provides the exact power include set. |
| M05 | «Прокладка кабеля, провода (Слаботочные сети) КГС» | No approved literal Table 1 include set: all candidates are candidate-only | Power/cross-category/unclear rows are candidate-only and never auto-included until owner provides the exact low-current include set. |
| M06 | «Монтаж металлоконструкций» | «Монтаж м/к фундаментов и ростверков»; «Монтаж м/к каркасов зданий и сооружений»; «Монтаж м/к эстакад»; «Монтаж малых конструктивных элементов м/к(монтаж жалюзийных решеток)» | Exclude exact «Монтаж м/к мачт-молниеотводов»; «Монтаж м/к антенных мачт»; «Изготовление м/к (прим. емкостей)». |
| M07 | «Сварка в нитку» | «сварка» + suffix | Exact or normalized prefix, e.g. «Сварка трубопровода Ду 300». |
| M08 | «Укладка трубопроводов (укладка)» | «Укладка трубопроводов» + suffix | Exact or normalized prefix with any continuation. |
| M09 | «Бетонные работы» | «Бетонирование фундаментов»; «Бетонирование фундаментов общего назначения» | Separate and traceable despite overlap with M02; de-duplicate identical source row. |
| M10 | «Обратная засыпка» | «Обратная засыпка траншеи под трубопровод» | No broadening to other backfill. |
| M11 | «Разработка траншеи» | «Разработка траншеи под трубопровод» | No broadening to other excavation. |
| M12 | «Монтаж опор ВЛ» | «Комплект анкерной концевой опоры» + suffix | Exact/prefix; never equal to «Монтаж железобетонных опор ВЛ» when measured in tonnes. |
| M13 | «Монтаж силового кабеля ВЛ» | «Прокладка самонесущего кабеля ВОЛС по стальным опорам» | Never auto-include; only explicit reassignment from M14 by the user. |
| M14 | «Монтаж ВОЛС ВЛ» | «Прокладка самонесущего кабеля ВОЛС по стальным опорам» | Default owner because source text explicitly says «ВОЛС». |

M13/M14 ownership is exclusive. Source-row key `(source_hash, sheet, row)` can contribute to only one Table-2 process. Manual reassignment to M13 atomically removes it from M14, recalculates both totals and records previous/new owner, actor, comment and rule version; double counting is a hard invariant violation.

## 5. Расчёт, деньги и статусы

- Количество и стоимость берутся из Table 1 за **весь период** через semantic headers. Единица Table 2 (в образце F) сравнивается с единицей каждой строки Table 1 (в образце J). Буквы F/J — fixtures, а не контракт координат.
- Для проверки единиц применяются NFKC, trim, схлопывание пробелов и case-fold, но не автоматическая конверсия. Физическое количество сначала суммируется по одобренным строкам с единицей Table 2. Если таких строк нет и у всех одобренных кандидатов одна общая альтернативная единица, их количество суммируется в этой единице, а ячейка единицы Table 2 становится красной и получает `исходная_единица/единица_Table1`. Если альтернативных единиц несколько, система показывает отдельный subtotal для каждой единицы; они никогда не складываются между собой, а пользователь выбирает одну unit-group прямым переключателем.
- Все суммы/количества — `Decimal`; суммируются сырые значения по строкам, и только затем стоимость один раз делится на `1_000_000` для вывода в млн RUB. Никаких float, округления по строкам или повторного деления. Внутренние агрегаты и coefficient check сохраняют полную точность. Только итоговые quantity/cost для UI и записи в отчёт округляются до двух знаков методом `ROUND_HALF_UP`: `1.234 → 1.23`, `1.235 → 1.24`. Manifest хранит и точное, и записанное значение.
- Денежная стоимость суммируется по всем одобренным строкам соответствия независимо от совпадения единиц. Unit mismatch не исключает стоимость, но остаётся видимым предупреждением и сохраняется в lineage.
- Коэффициент `2.7` — средний контрольный ориентир, а не преобразование стоимости и не строгая бухгалтерская проверка. После расчёта основной стоимости выполняется отдельная проверка `control_cost = (Table1_raw_cost_RUB / 1_000_000) × 2.7`. Если `control_cost >= Table2.K`, статус `cost_check_ok`; если меньше — `cost_check_warning`, который подсвечивается пользователю как повод проверить состав строк. Сама заносимая стоимость остаётся суммой Table 1, делённой на `1_000_000`, без умножения на `2.7`.
- Для warning сохраняются и показываются: исходная сумма Table 1 в млн RUB, coefficient, `control_cost`, Table2.K, абсолютная разница и lineage включённых строк. Проверка использует `Decimal` без промежуточного округления.
- UI показывает одно поле коэффициента на весь run со значением по умолчанию `2.7`; per-row коэффициентов нет. Изменение поля сразу пересчитывает все control statuses. `cost_check_warning` выделяется оранжевым, не блокирует export после отдельного явного acknowledgement пользователя. Значение коэффициента, warning evidence, actor/time acknowledgement и комментарий входят в manifest/audit.
- `Table2.J` и `Table2.L` сравниваются как числовые `Decimal`, не как текст. Оба значения округляются до двух знаков методом `ROUND_HALF_UP` только для этого сравнения; после округления точное равенство подсвечивается жёлтым без дополнительного tolerance. Форматы `1`, `1.0`, `1.000` равны; `0 = 0` также жёлтый. Две пустые ячейки считаются неизменившимися и тоже жёлтые; если пустая только одна, равенства и жёлтой подсветки нет. Пустое значение никогда автоматически не превращается в числовой ноль.
- Для выбранного месяца Table 2 должна иметь одну semantic pair: **«Количество»** и **«Общая стоимость»**. Preflight ищет пару по month/current-period header tree, а не по L/M или другим буквам. Если пары нет, export добавляет её справа от последнего отчётного блока и копирует структуру заголовка, merged cells, стили, number formats и ширины. Если пара существует, она используется повторно и дубликат не создаётся.
- Непустая существующая ячейка месяца никогда не перезаписывается молча. Review показывает `старое → рассчитанное`, разницу и lineage; запись нового значения разрешена только после явного подтверждения. Blank destination заполняется без overwrite confirmation. Все подтверждения и изменённые координаты входят в manifest/audit.
- Финальный deliverable — ровно один самостоятельный XLSX на основе Table 2. В нём должно быть `0` formula cells и `0` external workbook links/connections. Существующие формулы загруженной Table 2 заменяются в выходной копии их последними сохранёнными видимыми значениями; новые quantity/cost записываются только как числа. Стили, merged cells, filters, comments, colors и возможность вручную редактировать значения сохраняются. Internal manifest/audit остаётся в локальной SQLite и не выдаётся отдельным файлом.
- Если required Table-1 formula cell или любая Table-2 formula cell не имеет сохранённого видимого значения в data-only view, run/export блокируется. UI показывает source type, filename, sheet и cell coordinate и инструкцию открыть книгу в Excel, пересчитать, сохранить и загрузить заново. Система не подставляет blank/`0`, не исполняет формулу/макрос и не использует LibreOffice для автоматического пересчёта.
- Unit mismatch остаётся красным и содержит old/source. При единственной альтернативной единице количество суммируется в ней; при нескольких единицах используются раздельные subtotals и явный выбор одной группы. Стоимость всех одобренных строк включается независимо от выбранной quantity group. Отсутствие любого совпадения по наименованию даёт `0/0` и не подменяется unit mismatch. Missing saved value behind an input formula, malformed Decimal, duplicate lineage, missing/multiple candidate, ambiguous match и M13/M14 collision — blockers.
- Unit conversion не ожидается в нормальном потоке и по умолчанию отключена. Система никогда сама не выводит коэффициент для `км→м`, `т→кг` или другой пары. Конверсия разрешается только отдельным explicit owner action с exact normalized source/target units, Decimal factor, scope, version, evidence и rollback; после утверждения exact/raw/converted values входят в lineage. Без правила действует red slash и unit grouping.

## 6. Feedback memory, а не online training

Каждая строка-кандидат Table 1 показывается с наименованием, единицей, количеством, стоимостью, source file/sheet/row, причиной и уверенностью. Прямой checkbox **«Учитывать»** отражает `include=true/false`: рекомендуемые строки предварительно отмечены, сомнительные выделены и требуют подтверждения. Пользователь может снять/поставить галочку и добавить необязательный комментарий; итог пересчитывается детерминированно до экспорта.

Подтверждение inclusion/exclusion/выбора кандидата сохраняется как решение текущего run. Только отдельное явное действие **«Запомнить правило»** может создать versioned feedback rule; снятая галочка с комментарием лишь предлагает exclusion-кандидат и не создаёт reusable rule сама.

Минимальный ключ памяти: Table-2 category, normalized Table-1 item, stage/scope, units и baseline rule version. Active data компактны: canonical normalized entities в SQLite имеют integer IDs/FKs и hashes; каждая unique raw string хранится один раз/deduplicated; decision events ссылаются на IDs, а не копируют prose. Active rule records не содержат длинных raw text/prompts; append-only audit отделён от materialized active snapshot. Payload: rule id/version/status, include/exclude/candidate value, user, timestamp, source hash, comment, prior/new value и provenance. Перед reuse проверяются все ключи и schema/rule version compatibility. Несовместимый контекст, conflict, schema drift или duplicate rule — review blocker; правило не расширяется с одного item до всей категории и не применяется молча.

Есть undo текущего решения, deactivate feedback rule и rollback к прежней версии с audit trail. Deterministic retrieval сначала выполняется SQL с indexes по category/stage/unit/status/version; archived events исключены из AI prompt. Compaction/retention может архивировать inactive events и deduplicate raw strings, но никогда не удаляет financial lineage/audit; результат до/после compaction идентичен. Тесты обязаны доказывать reuse только в совместимом контексте, context isolation, conflict, rollback, schema drift, duplicate prevention, collision M13/M14, zero duplicate raw strings, storage growth per decision и retrieval latency на large corpus.

## 7. Gate 0 — решения владельца

До owner-approved записи запрещены scaffold и реализация. Владелец обязан решить: M04 exact power include set, M05 exact low-current include set и M04 supporting works; feedback reuse, compatible context и retention/rollback policy; configurable AI context/token budget. Exact/normalized-prefix suffix semantics, M14/M13 ownership, unit conversion, KS-6a scope, file selection, standalone output and prior rules уже утверждены. M02/M06 literals are fixed. Thresholds storage growth, retrieval latency и prompt tokens owner-approved, не implementation defaults.

## 8. Проверяемые инварианты

Результат order-independent; каждое значение имеет lineage; один source-row key имеет максимум одного Table-2 owner; export запрещён при unresolved blocker; rules/feedback versioned; original hash неизменён. Goldens 1006: сваи `261 / 37.313343`, бетон `2.36 / 0.034239`, ТТ `2138.059 / 33.75002661`, металлоконструкции `100.39863 / 12.59387023` (количество / млн RUB).
