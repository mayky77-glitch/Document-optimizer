---
type: task
status: planned
orda_status: frozen
card_id: qdrant-dense-rag-closure-fixes
version: 1
work_id: qdrant-dense-rag-closure-fixes-2026-08
task_id: dense-closure-contracts
purpose: Close CodeGraph-discovered cancel validation and evaluate_cases compatibility regressions.
role: worker
agent_role: developer
owner: qdrant-dense-closure-contracts
card_path: knowledge/tasks/qdrant-dense-rag-closure-fixes.md
branch: codex/qdrant-dense-closure-contracts
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: pending
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - src/report_processor/stage_rag/indexing.py
  - src/report_processor/stage_rag/evaluation.py
  - tests/unit/stage_rag/test_indexing.py
  - tests/unit/stage_rag/test_evaluation.py
forbidden_paths:
  - deploy
  - Dockerfile.embedding
  - compose.qdrant.yml
  - pyproject.toml
  - uv.lock
  - knowledge
tags:
  - task/implementation
  - status/planned
  - domain/rag
  - risk/high
links:
  - "[[qdrant-dense-rag-implementation-plan|Dense RAG plan]]"
---

# Dense RAG closure contract fixes

## Requirements

1. `ConfirmedExampleIndexer.cancel()` accepts only a non-string `Sequence` of
   opaque IDs, validates the complete sequence before `store.deactivate()`, and
   rejects sets, mappings, generators and path-like IDs without side effects.
2. Public `evaluate_cases()` preserves the legacy `(retriever, queries)` call
   form while one-argument fabricated-case evaluation remains rejected.
3. Add focused regression tests for both findings; preserve all other public
   contracts and production gates.

## Acceptance

- Focused indexing/evaluation tests pass.
- CodeGraph impact-guided Dense RAG contract/integration tests pass.
- Ruff and `git diff --check` pass for the changed scope.
- Exact feature SHA is accepted through a `--no-ff` integration merge.
