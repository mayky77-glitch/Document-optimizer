# Как безопасно определять родительские и ресурсные строки в КС-6а

## Scope and decision

Иерархический фильтр нужен, но не в форме «любая non-leaf строка — итог». Выбран role-aware frontier: явная колонка «№ п/п» задаёт структуру, «код вида затрат» отделяет работу от resource/equipment description.

## Search-space map and methods

Проверены четыре загруженные книги, run-артефакты, parser/filter/workflow/matcher и focused/full tests. XLSX читались отдельно с формулами и cached values; исходники не изменялись. Проверены leaf-only, hierarchy-off, unit+quantity и cost-reconciliation-only.

## Executive findings

- [Inference] Главный блокер создала ошибка schema detection: в 0907 колонка 182 «ВНР проверка ошибок» была принята за позицию вместо колонки 2 «№ п/п». Evidence: `synthesis-001`.
- [Inference] Non-leaf строка может быть реальной работой, а её дочерние строки — материалами. Evidence: `synthesis-003`.
- [Inference] Cost reconciliation полезна как диагностика, но не как selection predicate или blocker. Evidence: `academic-research-005`, `synthesis-004`.
- [Inference] После исправлений full dry run оставляет 6 реальных review-строк. Evidence: `synthesis-004`.

## Findings by lane

Search-space lane показал разные архетипы листов и опасность blanket filtering. Academic lane подтвердил, что filter срабатывает до matcher/review и потерянная parent-строка не возвращается. Synthesis lane нашёл точную schema-ошибку и source-native role.

## Contradictions and alternative explanations

Leaf-only убирает double count, но теряет работы с material children. Hierarchy-off возвращает section totals и equipment rows. Unit+quantity недостаточны без корректной schema; cost equality не определяет business role.

## Cross-lane synthesis

Лучшее решение — не компромисс между «удалять» и «не трогать», а двухпризнаковая модель: точная структура из «№ п/п» + row role из «кода вида затрат», с обязательным audit trail.

## Decision implications

1. Explicit alias «№ п/п» и fail-closed content fallback.
2. Section aggregate и resource/equipment не идут в matcher; кодированная work идёт.
3. Duplicate positions и excluded resources сохраняются в audit.
4. Hierarchy sums — non-blocking diagnostics.
5. Exact feedback повторно проверяет current unit policy.

## Gaps, assumptions, and limitations

Нет полной ручной ground-truth разметки. Cost-type policy подтверждена на текущих четырёх книгах; другой формат может потребовать отдельную policy. Число 6 — snapshot на 2026-08-06 при текущих rules/feedback/consensus.

## Evidence table and bibliography

- `search-space-scout-001..005`: структурный пересчёт и архетипы.
- `academic-research-001..006`: call-path, hypotheses, focused tests.
- `synthesis-001..005`: workbook columns, role policy, post-fix dry run, feedback policy.

## Final Step

1. Принять role-aware hierarchy как drawing-card policy.
2. Оставить 6 строк в ручной очереди.
3. Собрать ground truth для новых форматов.
4. Не внедрять финансовое автоподтверждение.
