---
type: task
status: done
orda_status: accepted
card_id: qdrant-dense-rag-audit-evaluation
version: 1
work_id: qdrant-dense-rag-audit-fixes-2026-08
task_id: dense-audit-evaluation
purpose: Replace fabricated candidate arithmetic with a reproducible observed-retrieval evaluation harness.
role: worker
agent_role: developer
owner: qdrant-dense-audit-evaluation
card_path: knowledge/tasks/qdrant-dense-rag-audit-evaluation.md
branch: codex/qdrant-dense-audit-evaluation
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
  - src/report_processor/stage_rag/evaluation.py
  - tests/fixtures/stage_rag/dense_rag_evaluation.json
  - tests/unit/stage_rag/test_evaluation.py
forbidden_paths:
  - src/report_processor/stage_rag/models.py
  - src/report_processor/stage_rag/qdrant_store.py
  - src/report_processor/stage_rag/indexing.py
  - deploy/qdrant
  - Dockerfile.embedding
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

# Dense RAG observed evaluation remediation

Run a deterministic sanitized query corpus through a real DenseRetriever boundary,
measure observed latency, and bind metrics to model/revision/index identity.

## Completion evidence

- Accepted feature: `0af721d6e46b84c5de5849ae0813384594bbbce7`.
- Accepted integration: `9fc6f51b4c0225c0e3ed22afdadf342044ade4c4`.
- Validation: 4 focused tests on the frozen branch and 54 combined post-merge
  tests with the accepted core identity contract passed.
