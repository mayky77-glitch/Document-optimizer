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
- Для проверки единиц применяются NFKC, trim, схлопывание пробелов и case-fold, но не автоматическая конверсия. Совпадение единиц делает строку допустимой для суммирования физического количества. При несовпадении ячейка единицы Table 2 становится красной и получает `исходная_единица/единица_Table1`.
- Все суммы/количества — `Decimal`; суммируются сырые RUB по строкам, и только затем результат один раз делится на `1_000_000` для вывода в млн RUB. Никаких float, округления по строкам или повторного деления.
- Desired comparison: `(Table1_raw_cost_RUB / 1_000_000 * 2.7) >= Table2.K`. Основание 2.7 (валюта, НДС, период) не утверждено: это **Gate 0 blocker**, не implementation default.
- Неизменённые `Table2.J` и `Table2.L` подсвечиваются жёлтым. Equality/tolerance, destination quantity и conversion policy — Gate 0 blockers; до решения жёлтый статус не является разрешением экспорта.
- Unit mismatch остаётся красным и содержит old/source. Включение количества и/или стоимости строки с несовпадающей единицей, конверсия и отображение нескольких разных source units остаются Gate-0 blockers. Duplicate lineage, stale formula/freshness failure, malformed Decimal, missing/multiple candidate, ambiguous match и M13/M14 collision — blockers.

## 6. Feedback memory, а не online training

Подтверждение inclusion/exclusion/выбора кандидата сохраняется как решение текущего run. Только отдельное явное действие **«Запомнить правило»** может создать versioned feedback rule; «Reject + comment» лишь предлагает exclusion-кандидат и не создаёт правило само.

Минимальный ключ памяти: Table-2 category, normalized Table-1 item, stage/scope, units и baseline rule version. Active data компактны: canonical normalized entities в SQLite имеют integer IDs/FKs и hashes; каждая unique raw string хранится один раз/deduplicated; decision events ссылаются на IDs, а не копируют prose. Active rule records не содержат длинных raw text/prompts; append-only audit отделён от materialized active snapshot. Payload: rule id/version/status, include/exclude/candidate value, user, timestamp, source hash, comment, prior/new value и provenance. Перед reuse проверяются все ключи и schema/rule version compatibility. Несовместимый контекст, conflict, schema drift или duplicate rule — review blocker; правило не расширяется с одного item до всей категории и не применяется молча.

Есть undo текущего решения, deactivate feedback rule и rollback к прежней версии с audit trail. Deterministic retrieval сначала выполняется SQL с indexes по category/stage/unit/status/version; archived events исключены из AI prompt. Compaction/retention может архивировать inactive events и deduplicate raw strings, но никогда не удаляет financial lineage/audit; результат до/после compaction идентичен. Тесты обязаны доказывать reuse только в совместимом контексте, context isolation, conflict, rollback, schema drift, duplicate prevention, collision M13/M14, zero duplicate raw strings, storage growth per decision и retrieval latency на large corpus.

## 7. Gate 0 — решения владельца

До owner-approved записи запрещены scaffold и реализация. Владелец обязан решить: M04 exact power include set, M05 exact low-current include set, M13/M14; stage и version-selection policy; лист/whole-period semantics; quantity destination/new-column meaning; coefficient 2.7 basis; J/L equality/tolerance; включение количества/стоимости строк с unit mismatch, conversion policy и формат нескольких source units; formula freshness/recalc policy; M03/M07/M08/M12 suffix semantics и M04 supporting works; display precision/overwrite; feedback reuse, compatible context и retention/rollback policy; configurable AI context/token budget. M02/M06 four literal variants already approved and are not reopened. Thresholds storage growth, retrieval latency и prompt tokens owner-approved, не implementation defaults.

## 8. Проверяемые инварианты

Результат order-independent; каждое значение имеет lineage; export запрещён при любом unresolved blocker; rules и feedback versioned; original hash неизменён. Goldens 1006: сваи `261 / 37.313343`, бетон `2.36 / 0.034239`, ТТ `2138.059 / 33.75002661`, металлоконструкции `100.39863 / 12.59387023` (количество / млн RUB).
