---
type: plan
status: in-progress
work_id: qdrant-dense-rag-2026-08-v2
owner: integration-owner
last_verified: 2026-08-03
updated: 2026-08-03
source_paths:
  - "src/report_processor/stage_rag/encoder.py"
  - "src/report_processor/stage_rag/retrieval.py"
  - "src/report_processor/drawing_card"
tags:
  - "task/implementation"
  - "domain/rag"
  - "layer/data"
  - "layer/infra"
  - "risk/high"
  - "status/in-progress"
links:
  - "[[../maps/architecture|Architecture]]"
  - "[[../DECISIONS|Decisions]]"
---

## Статус реализации

- Integration base: `648d3c95dbb4a7ed2ab27a7c4f1531b5f929102c`.
- Ветка: `codex/qdrant-dense-rag`.
- Gate 0: frozen; точный published SHA передаётся launch envelope после commit.
- Runtime `qdrant-dense-rag-2026-08` отменён до launch: envelope содержал
  несуществующий полный SHA. Исправленная работа: `qdrant-dense-rag-2026-08-v2`.
- Wave 1: `qdrant-dense-rag-core` и `qdrant-dense-rag-infra` запущены от
  `deedbf85f6508383cc7100753af9173eb0d22ebd`; scopes зарезервированы,
  P4 developer/high и P3 devops/medium работают параллельно.
- Оба первых agent turns завершились без diff из-за общего runtime usage limit;
  Orda записала no-progress без ложного evidence и выполнила единственный
  targeted retry каждого task ID.
- Targeted retries дали первые feature-коммиты: core
  `27ac4a6eaecd933821f5f92a92f97cb1ec546aea`, infra
  `b888c11c3ba981c96a976c2b23eb501bbd131a74`; их acceptance-наборы прошли,
  ветки опубликованы.
- Integration review не принял эти SHA: для core потребованы допустимый
  стабильный Qdrant point ID, cosine fallback, model/version/dimension filters,
  active lifecycle и согласованные protocols; для infra — versioned collection,
  payload indexes и строгая валидация embedding request/response. Обе задачи
  возвращены в `running` для одного additive remediation-коммита без rewrite.
- Infra remediation `3d256dd73bae857d66ce55d9a8db328d635021fc`
  прошла повторные pytest/Ruff/Compose/Bash проверки и ожидает merge.
- Core remediation `0bff4963b4a0c7397c95f2f5574e93cda776c088`
  закрыла основной список, но повторное isolation-review выявило, что point ID
  и deactivate ещё не включают tenant. Запущен последний bounded additive fix;
  SHA не будет принят до теста одинаковых public IDs в разных tenants.
- Финальный core SHA `89cb4814d04e31acb1143e7d75bc58f2b3e57df1`
  прошёл 25 focused tests, Ruff, format и diff-check; tenant входит в stable
  point ID/deactivate, а одинаковые public IDs разных tenants покрыты regression.
  SHA готов к `--no-ff` integration acceptance.
- Core принят Orda точной парой feature/integration:
  `89cb4814d04e31acb1143e7d75bc58f2b3e57df1` →
  `f35053baba2379864256ef428f5f4230e05a27eb`; merge имеет правильных двух
  родителей, повторные 25 focused tests прошли.
- Infra принята Orda точной парой `3d256dd73bae857d66ce55d9a8db328d635021fc`
  → `2488019e327445b8dc00f94c0df3540054557c2c`. Совместный Wave 1 набор:
  41 passed, 1 model-dependent skipped; Ruff, Compose config, Bash syntax и
  diff-check прошли. Этот integration SHA становится точной базой Wave 2.
- Wave 2 открывается для frozen задач `confirmed-indexer` и `app-integration`;
  production alias/deploy и реальные данные по-прежнему вне scope.
- Обе Wave 2 задачи зарезервированы и запущены от точного SHA
  `2488019e327445b8dc00f94c0df3540054557c2c` в отдельных ветках
  `codex/qdrant-dense-indexer` и `codex/qdrant-dense-app`; scopes не
  пересекаются, лимит Orda launch attempts исчерпан ровно по плану.
- Первый indexer SHA `379f97d8c0a4818727054ab108a8c0e5a1fcda3e`
  прошёл 5 тестов, но integration review не принял identity: ID от одного
  text hash схлопывает разные подтверждённые audits/contexts. Задача возвращена
  на один additive fix с tenant+audit identity и строгой lifecycle validation.
- Реальный локальный Qdrant 1.18.3 smoke-test выявил два infra-дефекта после
  Wave 1 acceptance: строковые payload schemas передавались как невалидный JSON,
  а образ не содержит `wget` для healthcheck. Integration owner исправляет два
  локализованных файла; обязательны повторный idempotency/snapshot smoke и health.
- Infra hotfix подтверждён реальным контейнером: health стал `healthy`, повторное
  создание collection/indexes идемпотентно, disposable snapshot restore прошёл.
- Финальный indexer SHA `1f159d0adc5714deb30c7d8c4643fed6141ffbcf`
  использует tenant+audit identity, сохраняет независимый text hash и прошёл
  18 focused tests; ожидает integration merge.
- App SHA `fbe7bcb69bb69455f56f5a6b2931f8098c8732b8` прошёл 7 тестов,
  но review отклонил перенос RAG category/score в поля решения. Запущен один
  additive fix: только evidence IDs/scores, category/confidences остаются пустыми,
  ответ проверяется по полному tenant/project/document/taxonomy context.
- Wave 2: `qdrant-dense-rag-indexer`, `qdrant-dense-rag-app` — ожидают Wave 1.
- Production deploy, реальные secrets и переключение production alias не выполнялись.

## Временные решения dev/test

1. Изоляция: общая versioned collection с обязательным server-side
   `tenant_id` filter; физическая изоляция остаётся совместимым расширением.
2. Ёмкость: настраиваемые batch/timeout/resource limits; production sizing
   остаётся нагрузочным gate, без выдуманной цифры первого года.
3. Качество: воспроизводимый обезличенный fixture и метрики Recall@5, MRR,
   top-1 error, review rate, latency; production thresholds остаются owner gate.
4. Модель: закреплённый RuBERT-tiny2 сохраняется как compatibility baseline,
   но не объявляется оптимальной production-моделью без holdout-сравнения.

# План: общий Qdrant и Dense RAG

## Цель

Перевести RAG из локального in-memory поиска в общий внутренний сервис с
постоянным векторным индексом. Система должна находить семантически близкие
подтверждённые примеры работ, но не должна самостоятельно менять договорные,
количественные или стоимостные решения.

Первый релиз включает Dense Retriever и Qdrant. Cross-Encoder не является
частью первого релиза: его можно добавить только после замеров качества
Dense Retriever на реальных подтверждённых данных.

## Подтверждённая исходная точка

- `stage_rag` уже является локальным Dense Retriever: локально закэшированный
  `cointegrated/rubert-tiny2` фиксированной ревизии создаёт 312-мерные векторы;
  поиск нормализует их и ранжирует cosine similarity с детерминированным
  tie-break.
- Текущий поиск пересчитывает и сравнивает векторы в памяти на запуске; он не
  имеет постоянной векторной базы, Qdrant, tenant-фильтров или жизненного цикла
  индекса.
- RAG предлагает только связи этапов для ручного `fit/not_fit`; Block 12 и
  явные feedback-решения остаются авторитетными.
- В `drawing_card` RAG сейчас отключён в административном workflow. Его
  включение не входит в этот план, пока не будет отдельно определён контракт
  классификации строк работ.

Следствие: работа является миграцией и расширением существующего Dense RAG,
а не заменой детерминированных правил или созданием RAG с нуля.

## Границы

Входит:

- общий Qdrant-сервер во внутренней сети;
- локальный embedding-service и постоянный индекс подтверждённых примеров;
- интерфейсы хранилища и retrieval, миграция `stage_rag` с brute-force cosine;
- фильтрация по компании/проекту/типу документа и версии таксономии;
- ручной review, аудит, метрики качества, Docker-образы и безопасный fallback.

Не входит:

- автоматическое утверждение финансовых или договорных решений;
- Cross-Encoder, генеративная LLM-классификация и внешние API;
- изменение правил Block 12, подсчётов, Excel/PDF-обработки или drawing-card;
- юридическая оценка действительности электронной подписи PDF.

## Целевая схема

```text
Детерминированные правила / точное feedback-решение
                    ↓ нет решения
Локальный embedding-service
                    ↓
Qdrant: Dense Retriever, top-5 + обязательные metadata filters
                    ↓
Карточка ручного review с кандидатами, score и доказательствами
                    ↓
Явное fit/not_fit → неизменяемый аудит → индексируемый confirmed example
```

Qdrant хранит только векторы и payload; embedding-service создаёт векторы.
Обращений к ChatGPT/OpenAI нет. «OpenAI-совместимый» локальный endpoint,
если он будет использоваться для другой модели, означает формат API, а не
внешний провайдер.

## Модель данных и изоляция

Каждая точка `confirmed_examples` должна содержать:

- стабильный `example_id` и хеш нормализованного текста;
- `tenant_id`, `project_id` (если применимо), `document_type`;
- нормализованный текст и только разрешённые для поиска контекстные поля;
- категорию/связь, решение review, `rule_version`, `taxonomy_version`;
- `embedding_model_id`, `embedding_model_revision`, размерность вектора;
- автора и время подтверждения, ссылку на аудит без серверного пути к файлу.

Каждый search-запрос обязан добавлять `tenant_id` как server-side filter.
Глобальный поиск между компаниями запрещён по умолчанию. Отдельная collection
на компанию нужна, если требования к изоляции не допускают доверия к
payload-фильтрам; иначе используется общая versioned collection с обязательным
tenant-фильтром.

## Этапы реализации

### P0. Контракт, данные для оценки и решения владельца

1. Зафиксировать публичные протоколы `EmbeddingProvider`, `VectorStore` и
   `Retriever`; существующий `StageEncoder` остаётся совместимым адаптером.
2. Собрать репрезентативный набор подтверждённых пар, включая аббревиатуры,
   похожие категории, разные единицы и негативные случаи.
3. Измерить baseline текущего локального retriever: Recall@5, MRR, latency,
   доля ошибочных top-1 и доля кандидатов, ушедших в review.
4. Владелец утверждает критерии успешности до переключения production-трафика.

**Готовность:** есть версионированный dataset без путей к исходникам и
воспроизводимый отчёт baseline.

### P1. Инфраструктура Qdrant

1. Поднять Qdrant в отдельном Docker-контейнере на общем внутреннем сервере.
2. Настроить persistent NVMe volume, API key, TLS/reverse proxy, firewall,
   healthcheck, snapshots и проверку восстановления snapshot.
3. Создать versioned collection, например `confirmed_examples_v1`, с cosine
   distance и payload indexes для обязательных фильтров.
4. Подготовить отдельные конфигурации `dev`, `test`, `prod`; адреса, ключи и
   tenant policy не попадают в Git или клиентские payload.

**Готовность:** test-клиент читает/пишет только разрешённый tenant; snapshot
можно восстановить в изолированной среде.

### P2. Локальные embeddings и индексатор

1. Проверить текущий RuBERT-tiny2 на P0-наборе. Его CLS-вектор не следует
   считать оптимальным sentence embedding без фактического сравнения качества.
2. Выбрать и зафиксировать локальную embedding-модель только по результатам
   этой оценки; указать ID, revision, размерность, pooling и лимиты текста.
3. Создать idempotent indexer: только подтверждённые manual-review решения
   создают/обновляют точки; отменённые либо заменённые решения деактивируют или
   версионируют точки, не переписывая аудит.
4. Встроить batch-переиндексацию в новую collection при смене модели,
   нормализации или таксономии; переключать alias только после проверки.

**Готовность:** повторный запуск не дублирует точки, а смена модели допускает
rollback на прежнюю collection.

### P3. Dense Retriever в приложении

1. Ввести Qdrant-адаптер за интерфейсом `VectorStore`; текущий in-memory
   retriever сохранить как test/dev fallback.
2. Для каждого запроса создавать локальный embedding, выполнять Qdrant search
   `top_k=5` с обязательными metadata filters и стабильной сортировкой.
3. Сохранить deterministic rules и exact feedback до RAG; RAG запускается
   только когда они не дали решения.
4. Возвращать в review candidate ID, score, нужный контекст и версию индекса;
   score не является основанием для автоматического включения работы.
5. При timeout/unavailable Qdrant/model выводить контролируемый статус и
   ручной review; поведение правил и расчётов не меняется молча.

**Готовность:** контрактные тесты доказывают tenant filtering, stable ordering,
отсутствие автоматического изменения решения и корректный fallback.

### P4. Shadow mode и ввод в эксплуатацию

1. Сначала выполнять новый поиск параллельно со старым и логировать только
   обезличенные технические метрики и IDs.
2. Сравнить качество P0-набора и реальные review outcomes; исправить
   нормализацию, метаданные или модель до включения UI.
3. Включить RAG только как рекомендацию для ограниченного tenant/проекта.
4. Отслеживать качество, задержку, model/index version, число подтверждений и
   отклонений; назначить владельца регулярного пересмотра метрик.

**Готовность:** критерии P0 достигнуты на holdout-наборе и pilot не создаёт
ни одного автоматического финансового/договорного решения.

### P5. Контейнеры и эксплуатация

1. Собрать отдельные образы `app`, `embedding-service`, `qdrant`; в dev
   использовать Compose, в production — согласованный механизм развёртывания.
2. Модель и её кэш не зашивать в кодовый образ без лицензии и контроля версии;
   использовать проверяемый model volume/образ и offline загрузку.
3. Настроить ограничения памяти/CPU, логи без исходного текста документов,
   ротацию, алерты Qdrant/model и runbook восстановления.

**Стартовая мощность:** один внутренний сервер 4 vCPU, 12–16 ГБ RAM и 50 ГБ
NVMe без GPU достаточен для небольшого/среднего пилота и последовательной
обработки. Ресурсы подтверждаются нагрузочным тестом на выбранной модели и
фактическом размере индекса.

### P6. Решение о Cross-Encoder

Cross-Encoder рассматривается только после P4. Добавлять его можно лишь если
Dense Retriever регулярно содержит верный пример в top-5, но неверно ранжирует
top-1. Тогда он rerank-ит только top-5 спорных кандидатов и также остаётся
recommendation-only.

**Стоп-критерий:** если Dense Retriever не проходит Recall@5, сначала
исправляются данные, нормализация, модель или filters; Cross-Encoder не служит
заменой плохого retrieval.

## Критичные моменты и нюансы

| Риск / нюанс | Требование плана |
| --- | --- |
| Ошибочная семантическая аналогия | Никакой RAG-score не меняет количество, стоимость или договорную позицию без review. |
| Утечка между компаниями | `tenant_id` обязательный server-side filter; тесты обязаны доказывать его во всех путях поиска. |
| Неподходящая embedding-модель | Нельзя принимать текущий CLS embedding как оптимальный по умолчанию; нужен holdout-бенчмарк. |
| Дрейф модели/таксономии | Вектор хранит model и taxonomy version; смена — новая collection + alias + rollback. |
| Дубли и противоречивые примеры | Upsert идемпотентный по стабильному ID; новое явное решение версионирует/деактивирует старое, аудит неизменяем. |
| Неработающий сервис | Controlled unavailable → ручной review/fallback; запрещено тихо подменять результат. |
| Аббревиатуры и коды | На P0-наборе отдельно проверить такие случаи; точные правила/feedback имеют приоритет над semantic retrieval. |
| Секреты и документы | API keys только в secret store; не логировать исходные пути, тексты документов или payload сверх необходимого. |
| Преждевременный Cross-Encoder | Не внедрять до подтверждённой проблемы reranking; он увеличивает latency и требования к ресурсам. |
| Высокая стоимость эксплуатации | Qdrant и embedding-service развёртываются отдельно и масштабируются независимо; GPU не является предпосылкой первого релиза. |

## Открытые решения владельца

1. Будет ли изоляция компаний логической (`tenant_id` filter) или физической
   (отдельная Qdrant collection/инстанс)?
2. Какой объём подтверждённых примеров и число одновременных запусков нужно
   поддержать в первый год?
3. Какой набор данных и целевые Recall@5 / допустимая доля review утверждаются
   как production gate?
4. Какая локальная embedding-модель проходит P0-бенчмарк и разрешена по
   лицензии/политике эксплуатации?
5. Кто владеет snapshots, ключами, SLO и пересмотром качества модели?

## Условие начала кода

К реализации переходить после закрытия хотя бы решений 1–4 и создания
отдельных implementation/test/infra задач. Этот документ не разрешает
переключать RAG или развёртывать общий сервер без отдельного согласования.
