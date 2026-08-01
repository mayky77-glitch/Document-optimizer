---
type: task
status: done
work_id: reconciliation-authoritative-classification-v3-final
role: orchestrator
agent_role: orchestrator
owner: root
profile: L3
routing_grade: P5
routing_reason: "Authoritative review required coordinated core, admin, UI and test contracts."
assigned_model: gpt-5.6-sol
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-sol
actual_reasoning_effort: medium
model_fallback: false
last_verified: 2026-08-02
updated: 2026-08-02
source_paths:
  - src/report_processor/reconciliation_review
  - src/report_processor/processing/reconciliation.py
  - src/report_processor/matching/models.py
  - src/report_processor/calculation/engine.py
  - src/report_processor/quality_control
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_feedback_store.py
  - src/report_processor/admin_panel/reconciliation_review_routes.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/assets/admin.css
  - tests/integration/test_reconciliation_authoritative_flow.py
  - tests/integration/test_reconciliation_review_ui_contract.py
  - tests/unit/reconciliation_review/test_authoritative_core.py
  - tests/unit/admin_panel/test_authoritative_review.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_feedback_store.py
  - tests/unit/admin_panel/test_reconciliation_state.py
depends_on:
  - reconciliation-authoritative-core-v3
  - reconciliation-authoritative-admin-v3
  - reconciliation-authoritative-tests-v3
tags:
  - task/implementation
  - status/done
  - domain/document-processing
  - capability/admin-panel
  - layer/backend
  - layer/frontend
  - risk/high
links:
  - "[[../maps/project-map|Карта проекта]]"
  - "[[reconciliation-manual-review-full-cards-v2|Заменённый journal-only подход]]"
---

# Authoritative ручная классификация сверки

## Продуктовый контракт

- Одна карточка объединяет глобальную группу всех исходных строк по
  нормализованному наименованию/общему началу и единице.
- Показаны предложенная категория, все строки, групповое решение и построчное
  исключение.
- Режим выбирается прямым двухпозиционным переключателем: «Количество + стоимость»
  или «Только стоимость».
- Решение меняет matching, calculation и итоговый XLSX. Feedback сохраняется
  только после успешной записи файла и подавляет повтор той же карточки.
- API и UI не раскрывают пути, листы, формулы, provenance и evidence; числа
  показываются с двумя знаками.

## Архитектура и приёмка

- Глобальная обработка осматривает target один раз, объединяет все sources, один раз
  выполняет matching/calculation/QC и один раз пишет output.
- Контракты вынесены из `app.py` и `service.py` в малые модули `reconciliation_*`.
- ORDA integration SHAs: backend/UI `f967b05`, `03ecf31`; core `24eb0be`; admin
  `daf333d`; focused tests `ff2f01f`.
- Focused acceptance: 24 tests passed; Ruff, Ruff format, Node syntax and diff-check
  passed. Полный suite не запускался.
- Browser smoke на production HTML/CSS/JS и синтетическом authoritative job:
  1440×900 и 390×844, light/dark, без горизонтального overflow и console errors.
  Проверены раскрытие всех трёх строк, два знака чисел,
  построчное исключение, `cost_only`, групповое принятие и нулевой
  unresolved gate. Технические metrics/warnings и privacy-поля в UI отсутствуют.

## Handoff

Заменяет journal-only карточки и массовые `upstream warning`. Источник истины — код
и целевые тесты на integration SHA `ff2f01f` и позже.
