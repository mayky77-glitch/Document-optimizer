---
type: component
tags:
  - knowledge/component
  - domain/drawing-card
  - layer/backend
  - capability/xlsx-output
  - capability/rag-feedback
last_verified: 2026-08-03
updated: 2026-08-03
source_paths:
  - src/report_processor/drawing_card
  - src/report_processor/admin_panel/drawing_card_service.py
  - tests/unit/drawing_card
  - tests/integration/test_drawing_card_admin.py
---

# Карточка остатков

## Каноническая рабочая копия

- Repository: `/Users/x/Documents/Сооотношение документов/Document-optimizer-ready`.
- Branch: `codex/drawing-card-summary-v1`.
- Production integration commit: `267437b` (`feat: add drawing card contract controls`).
- Extraction commits: `5f33ee4`, `4778c47`.
- CodeGraph: local `.codegraph/`; synchronized 2026-08-03 (487 files, 6,067 nodes,
  16,893 edges).

## Границы компонента

- `drawing_card/sources/`: схема, многоуровневые Excel-заголовки, извлечение Decimal.
- `drawing_card/matching/`, `review/`, `autopilot/`: классификация, RAG и явные feedback-правила.
- `drawing_card/aggregation/`: агрегация только по одобренным source row IDs.
- `drawing_card/output/`: layout, XLSX, summary, validation и exact numeric values.
- `admin_panel/drawing_card_service.py`: lifecycle приватной web-задачи.

## Завершённая инициатива

- Task: [[../tasks/drawing-card-contract-check-rag-plan]].
- PRD: [договорные значения и память RAG](../../docs/PRD_CONTRACT_VALUES_AND_RAG_FEEDBACK.md).
- Scope: четыре новых агрегата в существующих строках, допуск 1 000 руб.,
  conditional error sheet и исправление exact-feedback lifecycle.

## Rolling-история тестов

Хранить ровно два последних завершённых прогона. Полные логи и приватные пути в vault
не копировать.

1. 2026-08-03: full pytest `856 passed, 24 skipped, 2 failed in 46.65s`.
   Оба failure доказанно baseline/unrelated; source и test paths unchanged:
   MatchStrategy enum contract lacks `AUTHORITATIVE_REVIEW`, а hierarchy presentation
   omits actionable amounts.
2. 2026-08-03: focused after formatting `59 passed in 2.95s`; changed-scope Ruff,
   format check и diff-check clean. Full Ruff имеет только 3 pre-existing E501 в
   `tests/integration/test_drawing_card_ui_contract.py`; изменённые paths clean.
