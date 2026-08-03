---
type: task
status: done
orda_status: accepted
card_id: qdrant-dense-rag-indexer
version: 1
supersedes: null
work_id: qdrant-dense-rag-2026-08-v2
task_id: confirmed-indexer
purpose: Implement idempotent confirmed-example lifecycle, versioned reindex planning and reproducible Dense RAG evaluation.
role: worker
agent_role: developer
owner: "qdrant-dense-indexer"
card_path: knowledge/tasks/qdrant-dense-rag-indexer.md
card_commit_sha_ref: launch-envelope
base_sha_ref: wave-1-integration-sha
dependency_shas_ref:
  - wave-1-integration-sha
branch: codex/qdrant-dense-indexer
branch_base_sha_ref: wave-1-integration-sha
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-qdrant-dense-indexer"
profile: L2
routing_grade: P4
progress_revision: 5
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Idempotent lifecycle, versioned metadata and reproducible evaluation require difficult multi-file implementation."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - "src/report_processor/stage_rag/indexing.py"
  - "src/report_processor/stage_rag/evaluation.py"
  - "tests/fixtures/stage_rag/qdrant_fakes.py"
  - "tests/fixtures/stage_rag/dense_rag_evaluation.json"
  - "tests/unit/stage_rag/test_indexing.py"
  - "tests/unit/stage_rag/test_evaluation.py"
source_paths:
  - "src/report_processor/stage_rag/indexing.py"
  - "src/report_processor/stage_rag/evaluation.py"
  - "tests/fixtures/stage_rag/qdrant_fakes.py"
  - "tests/fixtures/stage_rag/dense_rag_evaluation.json"
  - "tests/unit/stage_rag/test_indexing.py"
  - "tests/unit/stage_rag/test_evaluation.py"
depends_on:
  - "qdrant-dense-rag-core"
forbidden_paths:
  - "src/report_processor/stage_rag/__init__.py"
  - "src/report_processor/stage_rag/encoder.py"
  - "src/report_processor/stage_rag/contracts.py"
  - "src/report_processor/stage_rag/models.py"
  - "src/report_processor/stage_rag/qdrant_store.py"
  - "src/report_processor/drawing_card"
  - "src/report_processor/admin_panel"
  - "pyproject.toml"
  - "uv.lock"
  - "knowledge"
contract_versions:
  input: ConfirmedExampleVector-1.0+VectorStore-1.0
  output: ConfirmedExampleIndexer-1.0+DenseRAGEvaluation-1.0
acceptance_commands:
  - "uv run pytest -q tests/unit/stage_rag/test_indexing.py tests/unit/stage_rag/test_evaluation.py"
  - "uv run ruff check src/report_processor/stage_rag/indexing.py src/report_processor/stage_rag/evaluation.py tests/fixtures/stage_rag/qdrant_fakes.py tests/unit/stage_rag/test_indexing.py tests/unit/stage_rag/test_evaluation.py"
  - "uv run ruff format --check src/report_processor/stage_rag/indexing.py src/report_processor/stage_rag/evaluation.py tests/fixtures/stage_rag/qdrant_fakes.py tests/unit/stage_rag/test_indexing.py tests/unit/stage_rag/test_evaluation.py"
  - "git diff --check"
tags:
  - "task/implementation"
  - "status/done"
  - "domain/rag"
  - "layer/data"
  - "risk/high"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Confirmed-example indexer and evaluation metrics

## Goal

Index only explicit confirmed review outcomes. Stable ID and normalized-text hash
make repeated upsert idempotent. Replacement/cancellation deactivates old search
state without mutating audit history. Model, revision, dimensions, rule and
taxonomy versions must be bound to every point. Provide new-collection reindex
planning and rollback-safe alias intent, never switch a real alias. Evaluate a
sanitized fixture with Recall@5, MRR, top-1 error, review rate and latency.

## Scope and instructions

- Modify only `write_scope` paths.
- No original file path, workbook name, secret or raw private dataset in fixtures/evidence.
- Production thresholds and embedding-model selection remain explicit owner gates.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: frozen indexer, evaluation, sanitized fixture and focused tests.
- Commands and tests run: 18 focused pytest; Ruff; format; diff-check.
- Result: accepted `1f159d0adc5714deb30c7d8c4643fed6141ffbcf` →
  `01c87761870b1e546728186a2536473850bd5a2a`.
- Risks or follow-up: production dataset, thresholds and real alias switch remain gates.

## Handoff

Leave this card in `review` until orchestration accepts the result.
