---
type: task
status: frozen
card_id: drawing-card-ux-wave4
version: 1
supersedes: null
work_id: drawing-card-ux-wave4-v1
task_id: formats-terms-filename
purpose: Make drawing-card formats, Russian report terminology, and the public download filename explicit and consistent.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave4.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 1ea32250903feb733c1a9ffac76044543f55121b
branch: codex/drawing-card-ux-wave4-implementation
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/assets/drawing-card.html
  - src/report_processor/admin_panel/assets/drawing-card.js
  - src/report_processor/admin_panel/assets/drawing-card-review.js
  - src/report_processor/admin_panel/assets/index.html
  - src/report_processor/admin_panel/assets/package-reconciliation.html
  - src/report_processor/admin_panel/assets/help.html
  - README.md
  - tests/unit/drawing_card/test_drawing_card_service_contract.py
  - tests/unit/admin_panel/test_reconciliation_verification.py
  - tests/integration/test_drawing_card_admin.py
  - tests/integration/test_drawing_card_ui_contract.py
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - src/report_processor/drawing_card
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - src/report_processor/admin_panel/drawing_card_review_payload.py
  - knowledge/INDEX.md
contract_versions:
  input: DrawingCardReviewServiceCore-3.0
  output: DrawingCardWave4UX-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/drawing_card/test_drawing_card_service_contract.py tests/unit/admin_panel/test_reconciliation_verification.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_ui_contract.py
  - uv run ruff check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/drawing_card_service.py tests/unit/drawing_card/test_drawing_card_service_contract.py tests/unit/admin_panel/test_reconciliation_verification.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_ui_contract.py
  - uv run ruff format --check src/report_processor/admin_panel/app.py src/report_processor/admin_panel/drawing_card_service.py tests/unit/drawing_card/test_drawing_card_service_contract.py tests/unit/admin_panel/test_reconciliation_verification.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_ui_contract.py
  - node --check src/report_processor/admin_panel/assets/drawing-card.js
  - node --check src/report_processor/admin_panel/assets/drawing-card-review.js
  - git diff --check
---

# Wave 4 formats, terms and Russian filename

Implement the safe option from section 8 of the untracked canonical specification at
`/Users/x/Documents/Сооотношение документов/Document-optimizer-ready/docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md`.
The drawing-card process continues to accept source `.xlsx`, `.xlsm`, `.xlsb` only and an existing
report `.xlsx` only. It must explicitly reject `.ods` and `.pdf`; copy must explain that LibreOffice
Calc `.ods` and optional PDF belong only to the separate Excel/PDF comparison process. Keep browser,
server, help, README and tests consistent. Do not claim unsafe XLSB formula parity.

On the first screen call the product `Отчёт (карточка остатков)`. In subsequent buttons, progress,
statuses, results and help use `отчёт` as the primary term. Preserve `карточка остатков` only where
the parenthetical explanation or an already-existing legacy input artifact genuinely needs it.
Always write `LibreOffice Calc`; never imply PDF is mandatory.

Keep the private result artifact `_RESULT_NAME = "drawing-card.xlsx"`. Public result download names
must be derived only from the normalized `job.period`: `Отчёт по остаткам за июль 2026.xlsx` for
`2026-07`, and `Отчёт по остаткам.xlsx` when no period is selected. Use the existing bounded filename
sanitizer and RFC 5987 `filename*=UTF-8''...` Content-Disposition helper; never derive the name from
uploaded filenames or expose paths. Review-file naming remains unchanged.

Tests must cover `.ods`/`.pdf` rejection, exact supported format copy, the localized period and
fallback names, UTF-8 header encoding, internal artifact stability, terminology, and the existing
download/path/private-file safety constraints.
