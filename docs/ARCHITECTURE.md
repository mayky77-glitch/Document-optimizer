# ARCHITECTURE

## Контуры и поток

`immutable import + hash → dual XLSX formula/data-only views → semantic preflight → normalized values + lineage → selector/rules → review → Decimal calculation → flatten Table 2 → standalone value-only XLSX → atomic save/reopen/internal manifest`.

CLI и local site вызывают одно ядро и дают полный ручной путь без GPT. Рекомендуемый MVP: Python core + FastAPI + лёгкие server-rendered components; отдельный SPA/React не нужен до доказанной UX-проблемы. Site has exactly two named upload zones: **«Дополнительный отчёт / Table 2»** accepts one report XLSX; **«Исходные KS / Table 1»** accepts a folder or ZIP of source XLSX files. CLI equivalent requires explicit `--report` and `--sources` args. Both surfaces require explicit stage and month/current-period input. Модули: `io/xlsx_adapter`, `schema/preflight`, `domain/model`, `files/selector`, `rules/registry`, `feedback/memory`, `matching/candidates`, `review/service`, `calc/decimal`, `export/atomic`, `verify/manifest`, `storage/sqlite`, `cli`, `site`. Независимые responsibility; executable file: review от 500 строк, hard limit 700.

## Data, calculation and decision contracts

Импорт знает Table 1 (КС-2/КС-3/КС-6а) и Table 2 (`Расчет доп отчета карточка 23 Хандюк.xlsx` / `Лист1`), не буквы Excel. Preflight resolves exactly one semantic KS-6a sheet and exactly one whole-period-construction merged-header block, accepting normalized spelling variants; KS-2/KS-3/current-month scopes are hard-excluded. Zero/multiple matches produce evidence and user resolution. Normalized row содержит source hash, chosen sheet/block, row, semantic fields, text, Decimal amount/unit and rule version. Calculation aggregates exact Decimal values and presentation quantizes final output.

SQLite хранит canonical normalized entities с integer IDs/FKs/hashes and deduplicated raw strings. Materialized indefinite active-rule snapshot отделён от append-only version events. Opposite decision, off/on and restore append events then rebuild snapshot; no physical event deletion. Active rows are short IDs/status/scope, history is excluded from GPT. Indexes cover process/item/stage/scope/unit/status/version; compaction must preserve deterministic snapshot and lineage.

## Review UX

Один экран и **одна таблица review**: над ней run coefficient. Каждая Table-1 candidate row показывает source/units/contributions/reason/confidence, checkbox **«Учитывать»** и optional comment. User-changed or explicitly confirmed uncertain rows show a direct default-on **«Запомнить»** switch; automatic confident rows do not. Switch off means run-only audit; on stages an exact scoped feedback event that becomes active only after successful export. Unit groups, cost warnings and file choices remain direct controls without modal/dropdown. Export stays disabled for unresolved blockers.

## Standalone value-only export contract

Импорт открывает formula view для обнаружения формул и data-only view для чтения последнего сохранённого значения. Table 1 отдаёт core только значения; формулы не пересекают adapter boundary. Экспорт создаёт новый путь и только одну Table-2 книгу. Month pair ищется/создаётся семантически; nonblank destination требует old→new decision. Перед сохранением каждая существующая формула Table 2 заменяется соответствующим saved visible value, новые результаты записываются числами, external links/connections удаляются. Styles, merged cells, filters, comments, colors и ручная редактируемость значений сохраняются. Atomic save → reopen verification утверждает `formula_count=0`, `external_link_count=0`, правильные значения/стили и unchanged input hashes. Internal manifest остаётся в SQLite; пользователю выдаётся только XLSX.

## GPT boundary

GPT optional/default-off и может только предложить schema/mapping candidate. `ModelGateway` имеет взаимозаменяемые режимы: `disabled`, локальный GPT-capable CLI, ручной copy/paste строгого JSON через GPT application и опциональный API. Ручной bridge экспортирует минимальный request JSON и принимает response JSON по той же схеме; он не даёт приложению доступ к файлам или денежным полям. Deterministic SQL lookup выполняется первым; если он разрешил правило, AI call не происходит. Иначе GPT получает только minimal compatible projection top candidates/rules, никогда не whole history/raw corpus, и укладывается в configurable per-call context/token budget из Gate 0. Версия schema строго задаёт allowed enum/field/range; malformed JSON, unknown fields, out-of-domain enum, missing evidence или incompatible schema отвергаются детерминированно. До review выполняются schema validation и deterministic revalidation against normalized rows/rules. Log содержит prompt hash, model id, gateway mode, schema version/hash, output hash, validation/rejection reason — без денежной информации. GPT не может выбирать файл, суммировать, принимать решение, создавать feedback rule или писать Excel; deterministic результат не имеет GPT fallback.

## Безопасность, отказы и CodeGraph

XLSX обрабатывается локально в ограниченном процессе; формулы/макросы не исполняются. Missing cached value behind any required Table-1 cell or any Table-2 formula to be flattened is a blocker containing file/sheet/cell evidence and recovery `Excel recalculate → save → re-upload`. Blank/zero substitution and LibreOffice/automatic recalculation are forbidden. XLSB в MVP блокируется. Явные состояния: schema drift, unsupported format, missing cached value, missing/multiple candidate, stage/month mismatch, rule collision, duplicate lineage, unit mismatch, Decimal failure, nonzero formula/external-link count after reopen, value/style/internal-manifest mismatch. Tests prove exact evidence, recovery, one-file delivery and unchanged inputs.

CodeGraph не устанавливается и не инициализируется сейчас: кода нет. Только после первого Python/TypeScript scaffold отдельный non-production gate запускает `codegraph init`; далее граф применяется для dependency map, blast radius и выбора regression tests. `.codegraph/` — локальный индекс, source/tests — истина.
