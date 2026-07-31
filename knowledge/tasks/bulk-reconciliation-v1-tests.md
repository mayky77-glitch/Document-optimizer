---
type: task
card_id: bulk-reconciliation-v1-tests
status: frozen
version: 1
work_id: bulk-reconciliation-v1
task_id: tests
purpose: "Зафиксировать bulk, multi-index, review, feedback, RAG и Excel-контракты"
role: worker
agent_role: tester
owner: bulk-reconciliation-tests
profile: L1
routing_grade: P3
routing_reason: "Independent regression suite for multipart limits, deterministic state, privacy and binary output."
card_path: knowledge/tasks/bulk-reconciliation-v1-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 0c3a135bcac8b929bd7056bec21c016b44e27e83
branch: codex/bulk-reconciliation-tests
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/fixtures/admin_panel
  - tests/fixtures/drawing_card
  - tests/unit/admin_panel
  - tests/unit/drawing_card
  - tests/unit/extraction
  - tests/unit/training_data
  - tests/unit/normalization
  - tests/unit/matching
  - tests/integration/test_admin_panel.py
  - tests/integration/test_drawing_card_admin.py
  - tests/integration/test_drawing_card_real_data.py
depends_on: []
forbidden_paths:
  - src
  - tests/conftest.py
  - docs
  - README.md
  - knowledge
  - pyproject.toml
  - uv.lock
  - .github
  - ".env*"
  - "**/*.xlsx"
  - "**/*.xlsm"
  - "**/*.xlsb"
contract_versions:
  input: ProcessingContract-17.1+DrawingCardInlineReview-1.0+DrawingCardRAG-1.0
  output: BulkReviewAcceptance-1.0
acceptance_commands:
  - "uv run ruff check tests/fixtures/admin_panel tests/fixtures/drawing_card tests/unit/admin_panel tests/unit/drawing_card tests/unit/extraction tests/unit/training_data tests/unit/normalization tests/unit/matching tests/integration/test_admin_panel.py tests/integration/test_drawing_card_admin.py"
  - "uv run ruff format --check tests/fixtures/admin_panel tests/fixtures/drawing_card tests/unit/admin_panel tests/unit/drawing_card tests/unit/extraction tests/unit/training_data tests/unit/normalization tests/unit/matching tests/integration/test_admin_panel.py tests/integration/test_drawing_card_admin.py"
  - "uv run pytest -q tests/unit/admin_panel tests/unit/drawing_card tests/unit/extraction tests/unit/training_data tests/unit/normalization tests/unit/matching tests/integration/test_admin_panel.py tests/integration/test_drawing_card_admin.py"
---

# Tests

Add tests for 1/32 source acceptance, 0/33 and unsafe input rejection, upload
order determinism, multiple document indexes in one workbook, legacy one-source
compatibility, stable review pagination, Russian presentation, reversible and
bulk decisions, explicit apply, private feedback across jobs, local-only RAG
with unavailable-model fallback, and no sensitive path leakage.

Verify the final workbook headers and order:
`Шифр чертежа`, `Наименование этапа работ`, `Ед. изм.`, `Количество`,
`Общая стоимость`. Verify integer quantity format `0`, fractional `0.###`, cost
format `#,##0.00`, and external real-file SHA-256/size/mtime immutability.
