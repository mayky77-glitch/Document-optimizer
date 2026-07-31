---
type: task
card_id: bulk-reconciliation-v1-design-parity
status: frozen
version: 1
work_id: bulk-design-parity-v1
task_id: design-parity
purpose: "Привести экран сверки документов к визуальному формату карточки остатков"
role: worker
agent_role: designer
owner: bulk-design-parity
profile: L1
routing_grade: P3
routing_reason: "Scoped CSS/markup parity using the accepted Gazprom design without API or behavior changes."
card_path: knowledge/tasks/bulk-reconciliation-v1-design-parity.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - dc410c8aaf0596ddd924c52ba6bbe9c912350b7f
branch: codex/bulk-design-parity
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/admin_panel/assets/admin.css
  - src/report_processor/admin_panel/assets/index.html
depends_on: []
forbidden_paths:
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/assets/drawing-card.css
  - src/report_processor/admin_panel/assets/drawing-card.html
  - src/report_processor/admin_panel/assets/drawing-card.js
  - src
  - tests
  - docs
  - README.md
  - knowledge
  - pyproject.toml
  - uv.lock
  - .github
  - ".env*"
contract_versions:
  input: AdminBulkReviewUI-1.0
  output: AdminGazpromDesignParity-1.0
acceptance_commands:
  - "git diff --check -- src/report_processor/admin_panel/assets/admin.css src/report_processor/admin_panel/assets/index.html"
---

# Design parity

Change design only. Make `/` visually match `/drawing-card`: same maximum width,
navigation, progress rail, Gazprom palette, typography, cards, upload fields,
buttons, errors, result panel, spacing, 360px layout, focus and reduced motion.
Do not change element IDs, form field names, JavaScript, API endpoints, text
meaning or processing behavior. Reuse shared visual patterns instead of CSS
patches that merely imitate one screenshot.
