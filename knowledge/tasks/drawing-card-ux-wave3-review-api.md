---
type: task
status: frozen
card_id: drawing-card-ux-wave3-review-api
version: 1
supersedes: null
work_id: drawing-card-ux-wave3-service-v1
task_id: review-api
purpose: Expose safe packet context, server categories, filters, metrics and adjacent rows to the accepted review UI.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave3-review-api.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 99fbf75fa9d0bca9026b78b07edb7bd6a56df32d
branch: codex/drawing-card-ux-wave3-review-api
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/drawing_card_review_payload.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - tests/integration/test_drawing_card_admin.py
  - tests/integration/test_drawing_card_review_api.py
forbidden_paths:
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/drawing_card
  - tests/unit/admin_panel/test_drawing_card_service.py
  - knowledge
  - docs
contract_versions:
  input: DrawingCardReviewServiceCore-3.0
  output: DrawingCardReviewApi-3.0
acceptance_commands:
  - uv run pytest -q tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_review_api.py tests/integration/test_drawing_card_ui_contract.py
  - uv run ruff check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/drawing_card_review_payload.py src/report_processor/admin_panel/drawing_card_presentation.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_review_api.py
  - uv run ruff format --check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/drawing_card_review_payload.py src/report_processor/admin_panel/drawing_card_presentation.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_review_api.py
  - node --check src/report_processor/admin_panel/assets/drawing-card-review.js
  - git diff --check
---

# Review API and presentation

Use the frozen service signatures from the service-core card. Parse and validate reason/category/
safe-filename/confidence/unresolved-only query parameters, pass them without reinterpretation to the
service and preserve page bounds. Add `GET /api/drawing-card/jobs/{job_id}/review/items/{review_id}/context`
with radius 1–5. Pass optional member version to `put_review_item`; keep old clients compatible.

Extend cluster presentation additively with `items`/`clusters`/`packets`, total/unresolved packet
aliases, `review_categories` and primitive `review_metrics`. Each packet exposes eligibility,
singleton/hazard state, match mode, unit compatibility, rules version and controlled differences.
Each member exposes only safe basename, sheet, row, position, drawing code, object index, work name,
unit, quantity, cost, confidence and controlled Russian reason/explanation. Never return an absolute
path, raw workspace location or source container path.

Keep the accepted browser assets unchanged. Its expected category schema is `id`, `label`, `units`;
filters are `reason`, `category`, `safe_filename`, decimal `confidence`, and boolean
`only_unresolved`. Adjacent context is returned only on explicit request. Tests must cover all
filters, safe context, Russian reason/confidence labels, category parity, metrics, stale member
version, radius bounds, additive backwards compatibility and path non-disclosure.
