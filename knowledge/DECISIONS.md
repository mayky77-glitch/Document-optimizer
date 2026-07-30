---
type: decisions
tags:
  - knowledge/decision
last_verified: 2026-07-30
updated: 2026-07-30
---

# Decisions

Record only accepted cross-cutting decisions. Link each decision to affected component cards and tasks; do not duplicate implementation detail here.

## DO-010: бизнес-правила остаются данными

Блок 10 принимает JSON и YAML, но после строгой валидации строит
одинаковые immutable models и canonical JSON bytes. YAML tags, anchors, aliases,
includes, environment interpolation и любые executable constructs запрещены.
Связанные карточки: [[tasks/document-optimizer-block-10-production]],
[[tasks/document-optimizer-blocks-09-10-tests]].
