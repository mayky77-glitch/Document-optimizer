---
type: task
status: review
orda_status: review
card_id: reconciliation-global-batch-review-v5-local-assist
version: 1
work_id: reconciliation-global-batch-review-v5-wave3
task_id: local-assist
purpose: Connect the verified local RuBERT encoder as a bounded non-authoritative reconciliation assist.
role: worker
agent_role: developer
owner: reconciliation-v5-local-assist
profile: L2
routing_grade: P4
progress_revision: 2
no_progress_count: 0
circuit_state: closed
routing_reason: Local-only model lifecycle, timeout and privacy boundaries require consequential integration work.
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: ""
card_path: knowledge/tasks/reconciliation-global-batch-review-v5-local-assist.md
base_sha_ref: wave3_card_commit_sha
branch: codex/reconciliation-v5-local-assist
branch_base_sha_ref: wave3_card_commit_sha
write_scope:
  - src/report_processor/admin_panel/reconciliation_semantic_assist.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_state.py
  - src/report_processor/admin_panel/reconciliation_batch_presentation.py
  - tests/unit/admin_panel/test_reconciliation_semantic_assist.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_batch_state.py
source_paths:
  - src/report_processor/reconciliation_grouping/semantic_model.py
  - src/report_processor/stage_rag/encoder.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_state.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/reconciliation_grouping
  - src/report_processor/stage_rag
  - pyproject.toml
  - uv.lock
contract_versions:
  input: ReconciliationPackageContract-1.0
  output: ReconciliationSemanticAssist-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/admin_panel/test_reconciliation_semantic_assist.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_batch_state.py tests/unit/reconciliation_grouping/test_semantic_model.py
  - uv run ruff check src/report_processor/admin_panel/reconciliation_semantic_assist.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_state.py src/report_processor/admin_panel/reconciliation_batch_presentation.py tests/unit/admin_panel/test_reconciliation_semantic_assist.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_batch_state.py
  - uv run ruff format --check src/report_processor/admin_panel/reconciliation_semantic_assist.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/reconciliation_state.py src/report_processor/admin_panel/reconciliation_batch_presentation.py tests/unit/admin_panel/test_reconciliation_semantic_assist.py tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_batch_state.py
  - git diff --check
last_verified: 2026-08-02
updated: 2026-08-02
tags:
  - task/implementation
  - status/review
  - domain/document-processing
  - capability/local-ai
  - risk/high
links:
  - "[[reconciliation-global-batch-review-v5-plan]]"
  - "[[reconciliation-global-batch-review-v5-core]]"
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Reconciliation global batch review v5 local assist

## Frozen contract

- Use only the already pinned, locally cached `RuBERTTiny2Encoder`; no download,
  public endpoint, prompt, workbook path, sheet, formula, coordinate or provenance.
- Run on a deterministic bounded subset of ambiguous normalized work names. Model
  failure, timeout or invalid output must leave packages and decisions usable.
- Model output may produce only a short presentation hint. It cannot change package
  membership, safe/manual status, category, mode, feedback, calculation or XLSX.
- Bind the pinned model revision into package version context without making model
  availability a required runtime dependency.
- Keep raw similarities and technical failure reasons private. Public payload may
  expose only a controlled Russian explanation string.
- Reuse the existing encoder and `LocalSemanticAssist`; do not add dependencies or
  grow `app.py`/`service.py`.

## Acceptance

- Tests prove identical deterministic packages with available, unavailable and
  timed-out local assist.
- Production smoke loads the pinned model with `local_files_only=True` and produces
  embeddings; a missing cache remains fail-soft.
- Public payload privacy contract remains unchanged except for a controlled hint.

## Completion evidence

- Changed paths: `reconciliation_semantic_assist.py`, bounded execution/state/
  presentation wiring, and the three owned admin-panel unit suites.
- Commands and tests run: frozen-card pytest (`25 passed, 1 skipped`; local model
  smoke requires `RUN_RAG_MODEL=1`), frozen-card Ruff check, Ruff format check,
  and `git diff --check`.
- Result: a deterministic maximum of eight ambiguous feature groups is sent in one
  local-only RuBERT batch with a bounded 10-second cold-load timeout. Similarities
  and technical failures are discarded; only a controlled Russian hint and opaque
  selected IDs remain in job state. The hint requires an actual comparable local
  result, so singleton and empty-similarity runs remain silent.
  Grouping, package safety, decisions, calculation and XLSX inputs are unchanged
  across available, unavailable, invalid and timed-out model outcomes.
- Risks or follow-up: live pinned-model smoke is intentionally skipped without
  `RUN_RAG_MODEL=1`; the adapter remains fail-soft when its local cache or optional
  RAG dependencies are unavailable.
