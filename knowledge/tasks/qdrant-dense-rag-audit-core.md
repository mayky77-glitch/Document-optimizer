---
type: task
status: draft
orda_status: frozen
card_id: qdrant-dense-rag-audit-core
version: 1
work_id: qdrant-dense-rag-audit-fixes-2026-08
task_id: dense-audit-core
purpose: Close confirmed-only, fail-safe replacement, opaque audit ID and index-evidence findings.
role: worker
agent_role: developer
owner: qdrant-dense-audit-core
card_path: knowledge/tasks/qdrant-dense-rag-audit-core.md
branch: codex/qdrant-dense-audit-core
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - src/report_processor/stage_rag/contracts.py
  - src/report_processor/stage_rag/models.py
  - src/report_processor/stage_rag/qdrant_store.py
  - src/report_processor/stage_rag/indexing.py
  - src/report_processor/drawing_card/matching/semantic.py
  - src/report_processor/drawing_card/matching/matcher.py
  - tests/unit/stage_rag/test_qdrant_store.py
  - tests/unit/stage_rag/test_indexing.py
  - tests/contract/test_dense_rag_contract.py
  - tests/integration/test_dense_rag_drawing_card.py
forbidden_paths:
  - deploy/qdrant
  - Dockerfile.embedding
  - compose.qdrant.yml
  - src/report_processor/stage_rag/service.py
  - src/report_processor/stage_rag/evaluation.py
  - tests/fixtures/stage_rag/dense_rag_evaluation.json
  - pyproject.toml
  - uv.lock
  - knowledge
tags:
  - task/implementation
  - status/in-progress
  - domain/rag
  - risk/high
links:
  - "[[qdrant-dense-rag-implementation-plan|Dense RAG plan]]"
---

# Dense RAG audit core remediation

Enforce confirmed-only storage/search, safe replacement ordering, opaque audit IDs,
and immutable index identity through manual-review evidence. Add regression tests
for rejected points, failed upsert, unsafe audit references and context evidence.
