---
type: task
card_id: bulk-reconciliation-v1-core
status: frozen
version: 1
work_id: bulk-reconciliation-v1
task_id: core
purpose: "Реализовать массовые источники, построчные индексы, inline-review, feedback и локальный RAG"
role: worker
agent_role: developer
owner: bulk-reconciliation-core
profile: L2
routing_grade: P4
routing_reason: "Cross-module processing and review state with privacy, deterministic Excel output and local semantic retrieval."
card_path: knowledge/tasks/bulk-reconciliation-v1-core.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 0c3a135bcac8b929bd7056bec21c016b44e27e83
branch: codex/bulk-reconciliation-core
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - src/report_processor/processing
  - src/report_processor/extraction
  - src/report_processor/training_data
  - src/report_processor/normalization
  - src/report_processor/matching
  - src/report_processor/drawing_card
depends_on: []
forbidden_paths:
  - src/report_processor/admin_panel/assets
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/view.py
  - tests
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
  input: ProcessingContract-17.0+DrawingCardAdminJob-1.0
  output: ProcessingContract-17.1+DrawingCardInlineReview-1.0+ReviewFeedbackStore-1.0+DrawingCardRAG-1.0
acceptance_commands:
  - "uv run ruff check src/report_processor/processing src/report_processor/extraction src/report_processor/training_data src/report_processor/normalization src/report_processor/matching src/report_processor/drawing_card src/report_processor/admin_panel/service.py src/report_processor/admin_panel/drawing_card_*.py"
  - "uv run ruff format --check src/report_processor/processing src/report_processor/extraction src/report_processor/training_data src/report_processor/normalization src/report_processor/matching src/report_processor/drawing_card src/report_processor/admin_panel/service.py src/report_processor/admin_panel/drawing_card_*.py"
  - "uv run python -m compileall -q src/report_processor"
---

# Core

Implement the frozen manifest contracts. Preserve all one-source public APIs.
Store uploads and feedback privately and atomically. The RAG implementation must
reuse the pinned local `cointegrated/rubert-tiny2` encoder, never make network
requests, never auto-accept a semantic suggestion, and fall back to existing
rules when dependencies or local model files are unavailable.

Inline review must expose bounded Russian presentation data, persist reversible
decisions, and apply only when no unresolved rows remain. Bulk approve applies
only to rows with a proposed category. Remember explicit user decisions without
storing filenames, paths, sheets, credentials or arbitrary payloads.

The final card must keep exactly these leading columns:
`Шифр чертежа`, `Наименование этапа работ`, `Ед. изм.`, `Количество`,
`Общая стоимость`. Integer quantity cells use `0`; fractional quantities use
`0.###`; costs use `#,##0.00`.
