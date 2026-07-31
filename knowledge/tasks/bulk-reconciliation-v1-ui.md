---
type: task
card_id: bulk-reconciliation-v1-ui
status: frozen
version: 1
work_id: bulk-reconciliation-v1
task_id: ui
purpose: "Сделать массовую загрузку и русскую проверку решений прямо в панели"
role: worker
agent_role: designer
owner: bulk-reconciliation-ui
profile: L2
routing_grade: P4
routing_reason: "Responsive high-volume review UI with accessibility, clear Russian actions and compact context."
card_path: knowledge/tasks/bulk-reconciliation-v1-ui.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 0c3a135bcac8b929bd7056bec21c016b44e27e83
branch: codex/bulk-reconciliation-ui
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/admin_panel/assets
depends_on: []
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/view.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - tests
  - docs
  - README.md
  - knowledge
  - pyproject.toml
  - uv.lock
  - .github
  - ".env*"
contract_versions:
  input: ProcessingContract-17.1+DrawingCardInlineReview-1.0
  output: AdminBulkReviewUI-1.0
acceptance_commands:
  - "node --check src/report_processor/admin_panel/assets/admin.js"
  - "node --check src/report_processor/admin_panel/assets/drawing-card.js"
  - "git diff --check -- src/report_processor/admin_panel/assets"
---

# UI

Use `$frontend-design` and Gazprom colors. Keep the interface minimal and fully
Russian. Reconciliation accepts up to 32 source files and one target file.

Drawing-card review stays inside the panel: paginated cards show category, work
name, quantity, source unit, target unit and total cost. Provide `Одобрить все`
and `Отклонить все`; per row provide `Одобрить`, `Отклонить`, `Изменить
категорию`, `Учитывать только стоимость` and undo. Use direct controls instead
of dropdowns for two-state choices. Localize technical diagnostics and show a
short corrective action. Preserve keyboard operation, visible focus, reduced
motion and 360px mobile layout.
