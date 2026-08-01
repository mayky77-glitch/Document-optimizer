---
type: task
status: done
work_id: upload-control-alignment-v1
role: worker
agent_role: designer
owner: "upload-control-designer"
profile: L2
routing_grade: P4
progress_revision: 3
state_fingerprint: "upload-controls-secondary-browser-verified"
no_progress_count: 0
circuit_state: closed
routing_reason: "L2 compatibility profile maps to P4."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: "Persistent designer profile; runtime did not expose child launch metadata."
model_fallback: false
last_verified: 2026-08-01
updated: 2026-08-01
write_scope:
  - "src/report_processor/admin_panel/assets/admin.css"
  - "src/report_processor/admin_panel/assets/drawing-card.css"
  - "tests/integration/test_block18_admin_panel.py"
  - "tests/integration/test_drawing_card_ui_contract.py"
  - "knowledge/maps/project-map.md"
source_paths:
  - "src/report_processor/admin_panel/assets/admin.css"
  - "src/report_processor/admin_panel/assets/drawing-card.css"
  - "tests/integration/test_block18_admin_panel.py"
  - "tests/integration/test_drawing_card_ui_contract.py"
  - "knowledge/maps/project-map.md"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Выравнивание загрузчиков и фирменные кнопки файлов

## Goal

На `/` верхние границы source/target upload inputs совпадают на desktop, а на
mobile поля складываются в одну колонку. На обеих страницах используются
нативные кнопки выбора файла в палитре интерфейса.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `admin.css`, `drawing-card.css` и два UI-contract теста.
- Commands and tests run: `uv run pytest -q tests/integration/test_block18_admin_panel.py tests/integration/test_drawing_card_ui_contract.py` (12 passed); `node --check` для `admin.js` и `drawing-card.js`; `git diff --check`.
- Result: `align-items: start` устраняет растяжение короткой label сеткой.
  Последний recovery заменяет full-height primary selector на компактный
  secondary upload: outer field 56px, `::file-selector-button` 40px,
  10px gap до имени файла, `--soft-blue`/`--input-border` вместо синего CTA.
  Hover, focus и 390px-компактный вариант сохранены; assertions фиксируют
  геометрию и secondary palette на обеих страницах.
- Risks or follow-up: focused тесты, Node и diff-check проходят. Root проверил
  компактный вариант в запущенном приложении и тёмной теме через Chrome:
  `/tmp/upload-compact-dark.png`. Поля выровнены, filename не конфликтует с
  кнопкой, selector визуально вторичен относительно основного CTA. Старые
  движки без `::file-selector-button` сохраняют доступный нативный control без
  брендовой подложки.

## Handoff

Accepted after focused tests and dark-theme browser verification.
