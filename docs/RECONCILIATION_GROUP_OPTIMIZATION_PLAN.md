---
type: plan
status: proposed
version: 1
updated: 2026-08-03
tags:
  - domain/document-processing
  - domain/rag
  - capability/reconciliation
  - capability/grouping
  - risk/high
---

# План сокращения ручных групп и обучения паттернов

## 1. Назначение

План предназначен для отдельного рабочего чата. Цель — сократить число ручных
решений при сверке строк без ослабления расчётных, финансовых и аудиторских
ограничений.

Целевой результат на текущем проверочном наборе:

- первый зрелый запуск: `30–50` верхнеуровневых групп вместо `211`;
- повторные похожие комплекты после накопления подтверждений: `15–30` групп;
- `0` известных запрещённых объединений;
- `100%` ненулевых релевантных строк доступны оператору;
- массовое и эквивалентное последовательное подтверждение дают одинаковый XLSX;
- RAG, шаблон или score по отдельности никогда не утверждают количество,
  стоимость, категорию или исключение.

## 2. Подтверждённая исходная точка

### 2.1 Каноническая копия

- Текущая записанная копия: `Document-optimizer-ready`.
- Ветка: `codex/drawing-card-summary-v1`.
- Зафиксированный HEAD: `648d3c95dbb4a7ed2ab27a7c4f1531b5f929102c`.
- После каждого принятого изменения требуется обновлять
  `knowledge/CURRENT_COPY.md` в той же задаче.

### 2.2 Кандидат Dense RAG

- Отдельная рабочая копия: `Document-optimizer-qdrant-dense-rag`.
- Ветка: `codex/qdrant-dense-rag`.
- Проверенный HEAD: `10eb20f00a63d6eb44714cc5a624d43809dfb665`.
- Реализация основана на каноническом HEAD, но ещё не записана как актуальная
  копия и должна пройти явную интеграцию.

Dense RAG уже предоставляет:

- локальный embedding-service и Qdrant;
- обязательную tenant/project/document/taxonomy изоляцию;
- индексирование только явно подтверждённых примеров;
- версии модели, таксономии и правил;
- замену и деактивацию устаревших примеров;
- Recall@5, MRR, top-1 error, review rate и latency;
- безопасный fallback;
- только кандидатов для ручной проверки, без автоматического изменения решения.

### 2.3 Текущая форма группировки

Принятые evidence текущего набора:

- 2 953 извлечённые строки;
- 989 видимых ненулевых строк;
- 250 точных review-групп;
- 212 semantic families;
- 211 decision packages;
- 3 безопасных массовых пакета;
- 208 пакетов требуют явного решения.

Основные причины дробления:

- reconciliation использует небольшой отдельный словарь действий и объектов;
- неизвестные action/object намеренно изолируются;
- нормализация различается между reconciliation и drawing-card;
- feedback применяется преимущественно по точному name+unit;
- числовые и технические параметры распознаются узко;
- различия модификаторов часто превращают обе стороны в исключения;
- RAG пока улучшает evidence, но не формирует безопасные пакеты;
- файлы `reconciliation_grouping`, `reconciliation_review`, review-clusters и
  `rules.json` в Dense RAG ветке не менялись.

### 2.4 Термины плана

- **Верхнеуровневая группа** — одна package-карточка, требующая максимум одного
  решения оператора для всех её безопасных участников.
- **Manual group** — package/family/group, содержащая хотя бы одну review-relevant
  строку без действующего решения.
- **Manual action** — одно явное действие оператора, после которого сокращается
  unresolved set. Открытие карточки и просмотр evidence действием не считаются.
- **Review-relevant строка** — ненулевая строка из пригодного источника в выбранном
  stage/scope, не закрытая non-overridable hazard или действующим точным решением.
- **Safe package** — пакет, где все участники проходят hard boundaries, pairwise
  constraints, cannot-link и version checks. Совпадения package key недостаточно.
- **Independent document set** — логически отдельный набор source+period+object,
  дедуплицированный приватными digest/identity без записи путей или имён в knowledge.
- **Confirmed outcome** — явное решение оператора, которое прошло authoritative
  apply и завершилось проверенным результатом. Autosave и RAG suggestion не являются
  confirmed outcome.
- **Critical modifier** — признак, способный изменить category, mode, unit
  compatibility или допустимость объединения.
- **Forbidden merge** — пара строк/групп, нарушающая hard constraint либо
  утверждённый cannot-link из regression fixture или подтверждённой истории.
- **Consequential version** — совокупность source/target digests, category catalog,
  canonicalization, ontology, typed-slot parser, pattern registry, taxonomy,
  embedding model и index identity versions.
- **Эквивалентные решения** — одинаковый итоговый набор row decisions после
  разрешения package/family/group/row precedence.
- **XLSX equivalence** — совпадение authoritative выбранных строк, Decimal-результатов
  и всех целевых ячеек/форматов, перечисленных действующим target schema и workbook
  validator. Если regression требует byte-identical archive, это более строгое
  требование сохраняется.

## 3. Неподвижные ограничения

1. Точные подтверждения и детерминированные запреты выше любого model score.
2. Несовместимые единицы, режимы, категории и критические модификаторы не
   объединяются автоматически.
3. Неизвестные единицы не считаются совместимыми только потому, что обе имеют
   состояние `unknown`.
4. RAG не считает деньги и количество, не применяет решение и не пишет XLSX.
5. Внешние AI API не получают тексты книг, пути, листы, формулы, координаты или
   provenance.
6. Нулевые строки остаются ephemeral и не создают feedback или отрицательное
   правило.
7. Каждая видимая строка входит ровно в одну точную группу и один итоговый путь
   package/family/group/row.
8. Любое старое решение становится stale при изменении consequential version.
9. Pattern promotion выполняется только после offline replay и допускает откат.
10. Производственные пороги качества и автоматизации утверждает владелец.

Нулевые ephemeral строки сохраняются в source partition, но не входят в invariant
видимого membership. Unsupported/hazard строки остаются доступны в отдельной
контролируемой очереди и не считаются успешно сгруппированными.

Нормативный порядок применения:

1. input integrity, formula/error hazards и non-overridable hard constraints;
2. текущее явное row decision;
3. текущее явное group decision;
4. текущее явное family decision;
5. текущее явное package decision;
6. точное активное feedback-решение при полном совпадении scope/version;
7. детерминированные ontology/rules;
8. active pattern registry;
9. hybrid lexical+dense evidence для ручного решения.

Hard boundary `category + mode + unit + primary action + primary object` необходим,
но недостаточен. После него обязательны modifier, slot, cannot-link и pairwise
проверки. Parse warning, пропущенный обязательный slot или неразрешённая
многозначность оставляют группу manual/exact-only.

## 4. Архитектурная идея

```text
Строки
  -> точная audit-нормализация
  -> semantic skeleton + typed slots
  -> hard boundaries и cannot-link ограничения
  -> exact feedback / deterministic rules
  -> pattern registry
  -> hybrid lexical+dense retrieval
  -> candidate clustering внутри hard boundary
  -> complete-linkage safety check
  -> packages + visible exceptions
  -> решения оператора
  -> authoritative calculation/XLSX
  -> confirmed feedback
  -> offline pattern mining/replay
```

Нужны две разные идентичности:

- `audit identity` сохраняет точный нормализованный термин и единицу;
- `semantic skeleton` удаляет только доказанные переменные параметры и нужен
  для поиска семейства. Он никогда не заменяет audit identity.

## 5. План выполнения

### Gate 0. Read-only канонизация и baseline

1. Подтвердить, какая копия является актуальной.
2. Проверить ancestry Dense RAG и составить точный integration range. На Gate 0
   ничего не merge/cherry-pick и не менять production code.
3. Прочитать принятые тесты/evidence обеих копий и определить команды повторной
   проверки после будущей интеграции.
4. На приватном наборе воспроизвести baseline: строки, точные группы, families,
   packages, safe/manual, unresolved и число действий.
5. Сохранить только обезличенные агрегаты. Термины и имена файлов не записывать
   в project knowledge.
6. Сформировать taxonomy причин manual review:

   - unknown action;
   - unknown object;
   - unknown/incompatible unit;
   - category missing/ambiguous;
   - critical modifier conflict;
   - typed modifier conflict;
   - exact feedback conflict;
   - RAG-only suggestion;
   - formula/error hazard;
   - unsupported source context.

**Обязательные артефакты Gate 0:**

- `knowledge/tasks/reconciliation-group-optimization-gate0.md` с HEAD, ancestry,
  integration range, владельцами, зависимостями и stop/go решением;
- приватный ignored baseline JSON с counts и version fingerprint;
- обезличенная aggregate-таблица причин в task card;
- frozen contracts, write scopes и acceptance-команды следующих waves.

**Stop condition:** канонический HEAD подтверждён, working tree состояние записано,
baseline totals воспроизводятся, сумма taxonomy причин согласована с manual count,
privacy prerequisites выполнены. До этого production implementation запрещена.

### Wave 0. Интеграция Dense RAG

1. Интегрировать только принятый диапазон `648d3c9..10eb20f` через проверяемую
   merge-историю; не выбирать случайные промежуточные коммиты.
2. Повторить focused Dense RAG, full regression, opt-in RuBERT, Qdrant live smoke,
   Ruff/format и diff-check.
3. Подтвердить, что defaults не включают production endpoint/alias и RAG остаётся
   review-only.
4. После принятого изменения интеграционный владелец обновляет
   `knowledge/CURRENT_COPY.md` в той же задаче: relative path, branch, новый HEAD,
   дата, clean/dirty status и краткое назначение. При uncommitted изменении
   записывается dirty status и краткий scope; metadata-only edit не рекурсивен.
5. Сохранить новый baseline и доказать отсутствие изменений authoritative XLSX.

### Wave 1. Единая нормализация и онтология

1. Создать один versioned canonicalization contract для reconciliation и
   drawing-card.
2. Унифицировать:

   - Unicode NFKC, `ё/е`, пробелы, дефисы, кавычки;
   - кириллические/латинские омографы в технических обозначениях;
   - безопасные опечатки только для длинных отличительных токенов;
   - склонения и доменные основы;
   - сокращения и аббревиатуры, scoped по категории/объекту.

3. Не копировать словари. Выделить единый versioned ontology resource.
4. Расширить действия: монтаж, прокладка, сварка, бетонирование, поставка,
   испытание, демонтаж, изготовление, надзор, окраска, изоляция, очистка,
   земляные работы, перевозка, подключение, наладка и выявленные corpus-действия.
5. Расширить объекты: кабель, провод, трубопровод, арматура, металлоконструкция,
   фундамент, оборудование, лоток, опора, муфта, изоляция, покрытие,
   автоматика, освещение, заземление и corpus-объекты.
6. Извлекать несколько действий/объектов:

   - primary action/object;
   - secondary actions/objects;
   - explicit semantic conflict.

7. Создать полную unit ontology:

   - canonical unit;
   - physical family;
   - scale;
   - разрешённые aliases;
   - запрещённые преобразования;
   - `unknown` как exact-only boundary.

**Тесты:** golden normalization, омографы, typo boundary, multi-label, unit
compatibility, unknown-unit isolation, обратная совместимость точных ID.

### Wave 2. Typed slots и semantic skeleton

1. Разобрать параметры:

   - `DN/Ду`, `D/d`, `Ø`, диаметр в мм;
   - `PN/Ру`, давление;
   - напряжение и диапазоны кВ;
   - кабельное сечение и число жил (`4×16`, `3х2,5`);
   - длина, масса, количество, марка, материал, исполнение;
   - ГОСТ/ТУ, класс огнестойкости, модель и артикул;
   - индекс/номер документа как non-semantic identifier.

2. Строить шаблон со слотами, например:

   ```text
   монтаж кабеля <cable_mark> <section> <voltage>
   монтаж трубопровода <diameter> <pressure> <material>
   ```

3. Для каждого slot указать влияние:

   - не меняет категорию;
   - разделяет semantic family;
   - является hard conflict;
   - только отображается оператору.

4. Сохранять audit text и извлечённые slots отдельно.

**Выход:** `semantic skeleton`, typed slots, parse warnings и versioned parser.

### Wave 3. Corpus profiler и candidate miner

Создать offline-инструменты:

- `scripts/profile_reconciliation_corpus.py`;
- `scripts/mine_reconciliation_patterns.py`;
- `scripts/evaluate_reconciliation_patterns.py`.

Profiler должен считать:

- частые неизвестные токены и n-grams;
- неизвестные action/object/unit;
- почти одинаковые имена, разделённые пунктуацией или параметром;
- группы с одинаковым решением, но разными формулировками;
- термины, создающие больше всего ручных действий;
- coverage действующей онтологии и каждого правила.

Candidate miner использует только подтверждённые outcomes и создаёт:

- synonym/abbreviation candidate;
- slot-template candidate;
- include/exclude candidate;
- split/merge candidate;
- critical-modifier candidate;
- must-link/cannot-link candidate;
- category-specific normalization candidate.

Поддержка кандидата не должна искусственно расти из-за копий одной и той же
строки в похожих документах. Нужна дедупликация по semantic identity и независимому
document-set identity.

Пример перехода:

```text
3 confirmed outcomes одной category/mode/unit family
  -> miner предлагает «монтаж кабеля <mark> <section>»
  -> shadow replay на истории и holdout
  -> owner проверяет positive/hard-negative examples
  -> owner_approved
  -> active только после нуля conflicts/forbidden merges
```

### Wave 4. Pattern registry и граф обратной связи

1. Ввести состояния:

   ```text
   proposed -> shadow -> owner_approved -> active -> suspended -> retired
   ```

2. Pattern record содержит:

   - version и fingerprint;
   - ontology/parser/model/taxonomy versions;
   - scope: category, action, object, unit family, document type;
   - template и slots;
   - positive support;
   - hard negatives и contradictions;
   - replay metrics;
   - owner approval;
   - activation/rollback metadata.

3. Хранить feedback graph:

   - `must-link` для подтверждённо одинаковых семантик;
   - `cannot-link` для отклонённых похожих терминов;
   - hard negatives индексировать в Qdrant отдельно от positive examples;
   - последнее точное решение выше обобщённого паттерна.

4. Не разрешать self-training: RAG-предложение без явного подтверждения не
   становится обучающим примером.

### Wave 5. Offline replay и promotion gates

Каждый candidate прогоняется по всей доступной истории до активации.

Обязательные метрики:

- support по независимым наборам;
- coverage строк и групп;
- precision по holdout;
- contradiction count;
- forbidden-merge count;
- manual groups/actions before/after;
- изменённые category/mode/unit decisions;
- authoritative calculation equivalence;
- XLSX equivalence для эквивалентных решений;
- deterministic repeatability;
- latency и индексный размер.

Определения метрик:

- `manual_group_count` — число manual package/family/group после полного построения;
- `manual_action_count` — минимальное число явных operator actions для достижения
  `unresolved_row_count = 0` при действующей иерархии решений;
- `coverage` — покрытые pattern строки / все review-relevant строки;
- `precision` — корректные pattern decisions / все pattern decisions на holdout;
- `forbidden_merge_count` — число пар внутри safe packages, нарушивших hard/cannot-link;
- `double_membership_count` — видимые строки более чем в одном итоговом пути;
- `operator_correction_rate` — исправленные active-pattern decisions / все применённые
  active-pattern decisions за фиксированную release window;
- `equivalence_failure_count` — число несовпадений authoritative decisions,
  Decimal outputs или проверяемых XLSX cells. Допуск равен нулю.

Baseline и holdout не пересекаются по independent document-set identity. Размер,
период наблюдения и release window фиксируются в Gate 0; менять их после просмотра
результата запрещено.

Предлагаемые начальные gates:

- `shadow`: минимум 3 согласованных подтверждения из минимум 2 независимых
  наборов, без hard conflict;
- `owner_approved`: явное подтверждение шаблона владельцем;
- `active`: ноль contradictions и forbidden merges на replay, 100% согласие по
  category/mode в scope, unit compatibility, успешный holdout;
- любой конфликт после активации переводит паттерн в `suspended`, но сохраняет
  аудит и точные решения.

Пороги являются стартовыми и должны быть утверждены владельцем после baseline.

### Wave 6. Hybrid retrieval и улучшение RAG

1. Объединить сигналы:

   - exact feedback;
   - deterministic ontology/pattern;
   - lexical masks/BM25 или token overlap;
   - Dense RAG;
   - hard-negative distance;
   - unit/category/document filters.

2. Использовать reciprocal rank fusion или другой детерминированный hybrid rank.
3. Хранить два представления:

   - embedding полного нормализованного термина;
   - embedding semantic skeleton.

4. Индексировать approved pattern prototypes/centroids отдельно от одиночных
   примеров. Это снижает влияние дублей и шумных формулировок.
5. Выдавать оператору:

   - ближайшие подтверждённые positive examples;
   - ближайшие hard negatives;
   - совпавшие slots;
   - короткую контролируемую причину;
   - расхождения, мешающие пакетному решению.

6. Cross-Encoder допускается только как отдельный эксперимент над top-5/top-10,
   если holdout докажет улучшение top-1 без нарушения latency и privacy.
7. Ни Dense score, ни reranker не активируют решение самостоятельно.

### Wave 7. Безопасное clustering и package optimizer

1. Сначала применить hard boundaries:

   ```text
   category + mode + compatible unit + primary action + primary object
   ```

2. Внутри boundary использовать category-aware complete linkage. Не использовать
   наивный transitive union-find.
3. Critical и typed modifiers сначала создают подсемейства. Они не должны
   автоматически делать ручными обе стороны.
4. Исключение отделяется от безопасного остатка пакета.
5. Unknown action/object может войти только в manual candidate family с видимым
   объяснением. После активного подтверждённого pattern он становится known.
6. Unknown unit остаётся exact-only и никогда не делает пакет safe.
7. Package optimizer максимизирует сокращение действий при ограничениях:

   - ноль cannot-link внутри safe package;
   - полный pairwise compatibility;
   - ограниченный размер пакета;
   - видимые outliers;
   - стабильные IDs и deterministic order.

8. Сравнить complete linkage, constrained agglomerative clustering и
   prototype-based assignment. Выбрать по replay, не по желаемому числу групп.

### Wave 8. Active learning и интерфейс оператора

1. Оператор должен подтверждать паттерн или пакет, а не сотни одинаковых строк.
2. Очередь сортировать по expected action reduction:

   - сколько строк/групп разблокирует решение;
   - стоимость и количество затронутых данных;
   - неопределённость и близость hard negative;
   - novelty/diversity, чтобы не показывать десять почти одинаковых вопросов;
   - частота повторения между документами.

3. Показывать сначала различия и исключения; полный состав раскрывается.
4. Карточка паттерна показывает:

   - шаблон и slots;
   - предлагаемую category/mode;
   - coverage;
   - независимую поддержку;
   - positive и negative примеры;
   - исключения;
   - прогноз сокращения действий;
   - `Принять шаблон`, `Оставить только для этого случая`, `Разделить`,
     `Отклонить`.

5. Массовое подтверждение разрешено только active patterns и safe packages.
6. Autosave, undo, stale-version checks и row override сохраняются.

### Wave 9. Acceptance и rollout

1. Запустить shadow mode без изменения решений.
2. Сравнить baseline и candidate result на текущем приватном наборе.
3. Проверить второй похожий набор для оценки повторного использования.
4. Утвердить production thresholds.
5. Активировать сначала только точные low-risk patterns.
6. Наблюдать:

   - число manual groups/actions;
   - долю pattern reuse;
   - contradiction/suspension rate;
   - operator correction rate;
   - Recall@5/MRR/top-1 error;
   - calculation/XLSX equivalence;
   - latency и Qdrant availability.

7. При ухудшении отключить alias/pattern version без удаления audit history.
8. После принятия обновить актуальную копию и project knowledge.

## 6. Предлагаемая структура модулей

Финальные имена уточнить после Gate 0. Не расширять `app.py` и другие монолиты.

```text
src/report_processor/reconciliation_grouping/
  canonicalization.py
  ontology.py
  typed_slots.py
  feedback_graph.py
  pattern_models.py
  pattern_registry.py
  pattern_mining.py
  replay.py
  hybrid_retrieval.py
  clustering.py
  optimizer.py
  metrics.py
```

Предлагаемые контракты:

- `TermCanonicalization-2.0`;
- `DomainOntology-1.0`;
- `TypedSlots-1.0`;
- `PatternCandidate-1.0`;
- `PatternRegistry-1.0`;
- `FeedbackGraph-1.0`;
- `GroupingReplay-1.0`;
- `DecisionPackage-2.0`.

## 7. Обязательная матрица тестов

### Нормализация

- `ё/е`, Unicode, дефисы, кавычки, NBSP;
- латиница/кириллица в DN/PN/марках;
- безопасная typo tolerance;
- сокращения только внутри scope;
- stable audit identity.

### Slots и ontology

- несколько действий/объектов;
- диаметры, давление, напряжение, сечения, диапазоны;
- semantic/non-semantic numbers;
- modifier split и hard conflict;
- unknown unit exact-only.

### Pattern registry

- proposed/shadow/active/suspended lifecycle;
- exact feedback precedence;
- contradiction suspension;
- version staleness и rollback;
- отсутствие self-training.

### Retrieval

- tenant/project/document/taxonomy isolation;
- lexical+dense fusion determinism;
- positive и hard-negative retrieval;
- unavailable/timeout fallback;
- score не меняет решение.

### Clustering

- complete pairwise compatibility;
- cannot-link never enters safe package;
- outlier не разрушает safe remainder;
- no duplicate membership;
- deterministic ordering/IDs;
- unknown work и unit остаются manual.

### Authoritative flow

- package/family/group/row precedence;
- mass и sequential equivalence;
- unchanged calculations and XLSX;
- zero activity remains ephemeral;
- feedback сохраняется только после проверенного результата;
- source files byte-identical.

## 8. Метрики завершения

Минимум для принятия:

- обязательное: текущий набор — не более `50` верхнеуровневых групп;
- целевое, не блокирующее безопасность: `30–45`;
- обязательное на повторном похожем наборе после feedback: не более `30`;
- целевое на повторном наборе: `15–30`;
- обязательное: не более `20` индивидуальных спорных решений;
- целевое: `10–20`;
- `0` forbidden merges;
- `0` строк с двойным membership;
- `100%` ненулевых релевантных строк доступны;
- одинаковый authoritative XLSX для эквивалентных решений;
- RAG outage не меняет расчёт и безопасные правила;
- все pattern changes versioned и rollback-safe.

Если цель по числу групп требует небезопасного объединения, выпускается большее
число групп. Безопасность выше compression target.

## 9. Рекомендуемый порядок приоритетов

1. Read-only Gate 0: каноническая копия, baseline, taxonomy и frozen contracts.
2. Интеграция Dense RAG и актуализация канонической копии.
3. Единая canonicalization/ontology/unit contract.
4. Typed slots и semantic skeleton.
5. Corpus profiler и pattern candidate miner.
6. Replay evaluator и pattern registry.
7. Feedback graph и hard negatives.
8. Hybrid retrieval.
9. Constrained clustering/package optimizer.
10. Active-learning UI.
11. Shadow rollout и production gates.

## 10. Запреты для рабочего чата

- Не менять расчётный движок ради сокращения групп.
- Не принимать решение только по similarity/confidence.
- Не загружать приватные данные во внешний AI.
- Не активировать pattern без replay и owner approval.
- Не считать `unknown` совместимым с другим `unknown`.
- Не скрывать исключения ради достижения целевого числа групп.
- Не писать реальные термины, имена файлов и пути в project knowledge.
- Не включать production Qdrant alias, secrets или deployment без отдельного
  разрешения владельца.
- Не создавать новый монолит в `app.py`, service или frontend.

## 11. Стартовый запрос для другого чата

```text
Работай по плану docs/RECONCILIATION_GROUP_OPTIMIZATION_PLAN.md.

Сначала выполни только Gate 0: проверь AGENTS.md, knowledge/INDEX.md,
knowledge/CURRENT_COPY.md, актуальные worktrees/ветки, ancestry Dense RAG,
исходный baseline групп и причины manual review. Не начинай реализацию до
подтверждения канонической копии, воспроизводимого baseline и frozen контрактов.

После Gate 0 предложи bounded задачи с непересекающимися write scopes,
acceptance-командами и очередностью зависимостей. Сохраняй точные правила,
финансовые ограничения и authoritative XLSX. RAG остаётся assistive;
автоматизация разрешена только через versioned pattern, offline replay,
hard constraints и явное owner approval. После каждого изменения актуальной
копии обновляй knowledge/CURRENT_COPY.md в той же задаче.
```

## 12. Решения владельца перед активацией

Не блокируют Gate 0 и shadow-разработку, но нужны до production activation:

1. Минимальное число независимых подтверждений для active pattern.
2. Допустимые Recall@5, MRR, top-1 error и review rate.
3. Какие категории и pattern types разрешены для первой low-risk волны.
4. Максимальный размер одного safe package.
5. Кто подтверждает pattern promotion и владеет rollback.
6. Когда `Document-optimizer-qdrant-dense-rag` становится канонической копией
   либо интегрируется в другую копию.

Решения фиксируются в versioned activation checklist с датой и владельцем.
Thresholds, pattern scopes и package size по умолчанию задаются отдельно для
категории/семейства; глобальный порог разрешён только если holdout докажет его
одинаковую безопасность во всех затронутых категориях.

До начала waves должны быть назначены:

- integration owner;
- domain owner для category/unit/pattern semantics;
- privacy reviewer;
- pattern promotion/rollback owner;
- владелец representative private baseline и второго независимого holdout;
- владелец Qdrant snapshots, index identity и operational runbook.
