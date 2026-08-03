---
type: task
status: done
orda_status: accepted
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
progress_revision: 2
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
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
  - status/done
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

## Completion evidence

- Accepted feature: `d6bab7ebb161de2604d82700176b07dbb59d22c7`.
- Accepted integration: `453c8d9f5a2fe849c112661d5ca7426b050ef6c3`.
- Scoped tests: 51 passed; CodeGraph-guided post-merge set: 95 passed,
  3 environment/model-dependent skipped.
- Full regression: 928 passed, 24 skipped, exactly two documented unrelated
  baseline failures; opt-in RuBERT: 10 passed.
- Scoped Ruff/format/diff-check passed; full Ruff retained exactly three
  documented unrelated E501 baseline errors.
