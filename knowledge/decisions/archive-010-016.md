---
type: decisions
tags:
  - knowledge/decision
  - status/accepted
last_verified: 2026-08-16
updated: 2026-08-16
---

# Архив решений DO-010—DO-016

## DO-010: бизнес-правила остаются данными

JSON и YAML после строгой валидации дают одинаковые immutable models и canonical JSON. YAML tags,
anchors, aliases, includes, environment interpolation и executable constructs запрещены.

## DO-011: сводный XLSX публикует готовые числовые значения

Пользовательский файл не содержит формул; внутренняя математика остаётся в рублях, публикация — в
миллионах. Стоимость суммируется независимо от единицы, количество — только при одной точной
непустой единице для всех участников. Иначе публикация блокируется.

## DO-012: тема и решение по группе управляются напрямую

Тема хранится локально. Нерешённая группа имеет один поток выбора категории/режима и явного
применения либо отклонения; layout обязан переноситься без горизонтального overflow.

## DO-013: последнее явное review-решение является правилом

Новое явное решение по normalized name + unit заменяет старое и имеет приоритет над встроенным
примером. Пути, имена файлов и исходные пользовательские строки не копируются в knowledge.

## DO-014: договорные значения и feedback публикуются детерминированно

Contract и period rows используют Decimal/рубли внутри и миллионы только на выходе. Replay требует
точного normalized name + unit; другая единица остаётся ручной проверкой.

## DO-015: claims проверки и сверки разделяются

`verify` и `reconcile` — разные контракты. Доказательства writer/reconcile не доказывают verdict
verification. Это решение привело к отдельному числовому oracle в DO-017.

## DO-016: PropExtract используется только как источник методик

Допустимы методические идеи exact-or-ambiguous identity, provenance, consensus и adversarial tests,
но не предметные правила или код. Закрытые phrase allowlists запрещены; неизвестность fail-closed.
Code reuse требует отдельного лицензионного разрешения.

Связанные карточки: [[../components/drawing-card]], [[../components/document-verification]],
[[../tasks/reconciliation-max-accuracy-audit-v1]],
[[../research/propextract-methods-2026-08-13]].
