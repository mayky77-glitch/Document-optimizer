---
type: task
status: done
orda_status: accepted
card_id: qdrant-dense-rag-core
version: 1
supersedes: null
work_id: qdrant-dense-rag-2026-08-v2
task_id: dense-core
purpose: Implement public Dense RAG contracts, Qdrant REST storage, mandatory tenant filters and deterministic fail-safe retrieval.
role: worker
agent_role: developer
owner: "qdrant-dense-core"
card_path: knowledge/tasks/qdrant-dense-rag-core.md
card_commit_sha_ref: launch-envelope
base_sha_ref: published-base-sha
dependency_shas_ref:
  - published-base-sha
branch: codex/qdrant-dense-core
branch_base_sha_ref: published-base-sha
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-qdrant-dense-core"
profile: L2
routing_grade: P4
progress_revision: 8
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Multi-file vector storage contract with mandatory tenant isolation and fail-safe retrieval."
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
  - "src/report_processor/stage_rag/contracts.py"
  - "src/report_processor/stage_rag/models.py"
  - "src/report_processor/stage_rag/errors.py"
  - "src/report_processor/stage_rag/qdrant_store.py"
  - "src/report_processor/stage_rag/retrieval.py"
  - "tests/unit/stage_rag/test_qdrant_store.py"
  - "tests/contract/test_dense_rag_contract.py"
source_paths:
  - "src/report_processor/stage_rag/contracts.py"
  - "src/report_processor/stage_rag/models.py"
  - "src/report_processor/stage_rag/errors.py"
  - "src/report_processor/stage_rag/qdrant_store.py"
  - "src/report_processor/stage_rag/retrieval.py"
  - "tests/unit/stage_rag/test_qdrant_store.py"
  - "tests/contract/test_dense_rag_contract.py"
depends_on: []
forbidden_paths:
  - "src/report_processor/stage_rag/__init__.py"
  - "src/report_processor/stage_rag/encoder.py"
  - "src/report_processor/drawing_card"
  - "src/report_processor/admin_panel"
  - "tests/integration"
  - "pyproject.toml"
  - "uv.lock"
  - "knowledge"
contract_versions:
  input: StageRelationRAG-18.0
  embedding: EmbeddingProvider-1.0
  store: VectorStore-1.0
  output: DenseRetriever-1.0
acceptance_commands:
  - "uv run pytest -q tests/unit/stage_rag/test_retrieval.py tests/unit/stage_rag/test_qdrant_store.py tests/contract/test_dense_rag_contract.py"
  - "uv run ruff check src/report_processor/stage_rag/contracts.py src/report_processor/stage_rag/models.py src/report_processor/stage_rag/errors.py src/report_processor/stage_rag/qdrant_store.py src/report_processor/stage_rag/retrieval.py tests/unit/stage_rag/test_qdrant_store.py tests/contract/test_dense_rag_contract.py"
  - "uv run ruff format --check src/report_processor/stage_rag/contracts.py src/report_processor/stage_rag/models.py src/report_processor/stage_rag/errors.py src/report_processor/stage_rag/qdrant_store.py src/report_processor/stage_rag/retrieval.py tests/unit/stage_rag/test_qdrant_store.py tests/contract/test_dense_rag_contract.py"
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

# Dense RAG contracts and Qdrant vector store

## Goal

Add versioned protocols and immutable DTOs for local embeddings, confirmed-example
vectors, filtered search and retrievers. Implement a dependency-free Qdrant REST
adapter plus in-memory fallback. Every backend query must contain an exact
`tenant_id` must-filter. Validate model/taxonomy/vector metadata, reject unsafe
audit paths, use bounded timeouts and map failures to controlled RAG errors.

## Scope and instructions

- Modify only `write_scope` paths.
- Preserve existing `StageRelationRAG-18.0` API and deterministic in-memory tests.
- Return candidates only: `requires_manual_review=True`, `auto_accepted=False`.
- Stable order is score descending, then public `example_id`.
- Do not log text, payloads, paths, API keys or HTTP response bodies.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: frozen `stage_rag` contracts/store/retrieval scope and focused tests.
- Commands and tests run: 25 focused pytest; Ruff; format; diff-check.
- Result: accepted `89cb4814d04e31acb1143e7d75bc58f2b3e57df1` →
  `f35053baba2379864256ef428f5f4230e05a27eb`.
- Risks or follow-up: production isolation model and capacity remain owner gates.

## Handoff

Leave this card in `review` until orchestration accepts the result.
