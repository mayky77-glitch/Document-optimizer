---
type: task
status: done
orda_status: accepted
card_id: qdrant-dense-rag-final-audit-core
version: 1
work_id: qdrant-dense-rag-final-audit-fixes-2026-08
task_id: dense-final-core
purpose: Preserve public compatibility and close unavailable identity, evaluation and lifecycle validation findings.
role: worker
agent_role: developer
owner: qdrant-dense-final-core
card_path: knowledge/tasks/qdrant-dense-rag-final-audit-core.md
branch: codex/qdrant-dense-final-core
profile: L2
routing_grade: P4
progress_revision: 4
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
  - src/report_processor/stage_rag/contracts.py
  - src/report_processor/stage_rag/models.py
  - src/report_processor/stage_rag/qdrant_store.py
  - src/report_processor/stage_rag/retrieval.py
  - src/report_processor/stage_rag/indexing.py
  - src/report_processor/stage_rag/evaluation.py
  - src/report_processor/stage_rag/__init__.py
  - src/report_processor/drawing_card/matching/semantic.py
  - tests/unit/stage_rag
  - tests/contract/test_dense_rag_contract.py
  - tests/integration/test_dense_rag_drawing_card.py
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

# Dense RAG final contract and lifecycle remediation

Preserve old positional/public APIs, expose immutable store identity on unavailable
results, reject outages in quality evaluation, and validate replacement ID sequences
before any encode, upsert or deactivate side effect.

## Completion evidence

- Accepted feature: `36ca15677848e98a66a699b914478857d5570932`.
- Accepted integration: `4132e9eee50ec7a81a1d42433ef24b0ed7f799ab`.
- Validation: 77 scoped and 79 CodeGraph-guided tests passed; one opt-in model
  test was skipped in the guided run and passed in the separate RuBERT run.
