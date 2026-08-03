---
type: task
status: done
orda_status: accepted
card_id: qdrant-dense-rag-audit-infra
version: 1
work_id: qdrant-dense-rag-audit-fixes-2026-08
task_id: dense-audit-infra
purpose: Close loopback, restore, collection schema, embedding request and reproducible image findings.
role: worker
agent_role: devops
owner: qdrant-dense-audit-infra
card_path: knowledge/tasks/qdrant-dense-rag-audit-infra.md
branch: codex/qdrant-dense-audit-infra
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
  - deploy/qdrant
  - Dockerfile.embedding
  - .dockerignore
  - compose.qdrant.yml
  - pyproject.toml
  - uv.lock
  - src/report_processor/stage_rag/service.py
  - tests/unit/stage_rag/test_embedding_service.py
forbidden_paths:
  - src/report_processor/stage_rag/models.py
  - src/report_processor/stage_rag/qdrant_store.py
  - src/report_processor/stage_rag/indexing.py
  - src/report_processor/stage_rag/evaluation.py
  - src/report_processor/drawing_card
  - knowledge
tags:
  - task/implementation
  - status/done
  - domain/rag
  - layer/infra
  - risk/high
links:
  - "[[qdrant-dense-rag-implementation-plan|Dense RAG plan]]"
---

# Dense RAG audit infrastructure remediation

Parse exact loopback URLs, validate collection/vector/index schemas, test a canary
through destructive disposable restore, require the pinned model field, and build
a locked CPU-only embedding image with a minimal context.

## Completion evidence

- Accepted feature: `f1ad3accb55fc5cb86e14e2db1d016e6f305c35a`.
- Accepted integration: `f4e46fc97501bfd569a27b9be96b09962eef6a54`.
- Validation: 6 focused tests, URL suite, Qdrant 1.18 live restore/schema checks,
  Compose/Ruff/lock checks and CPU-only Docker build passed.
