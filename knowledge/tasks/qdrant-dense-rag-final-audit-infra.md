---
type: task
status: done
orda_status: accepted
card_id: qdrant-dense-rag-final-audit-infra
version: 1
work_id: qdrant-dense-rag-final-audit-fixes-2026-08
task_id: dense-final-infra
purpose: Prevent proxy-environment API-key exfiltration from loopback Qdrant scripts.
role: worker
agent_role: devops
owner: qdrant-dense-final-infra
card_path: knowledge/tasks/qdrant-dense-rag-final-audit-infra.md
branch: codex/qdrant-dense-final-infra
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
  - deploy/qdrant/scripts
forbidden_paths:
  - src
  - tests
  - pyproject.toml
  - uv.lock
  - Dockerfile.embedding
  - compose.qdrant.yml
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

# Dense RAG final proxy remediation

Make every authenticated local Qdrant curl bypass all proxy environment variables
and prove hostile HTTP/HTTPS/ALL proxy settings cannot receive the API key.

## Completion evidence

- Accepted feature: `044447f34c13d9e5aaa8f8c7476170b5ae9dfbf1`.
- Accepted integration: `b45e78f34701574154f38eeb6d586dfa3f601d3e`.
- Validation: Bash/URL/proxy capture and hostile-proxy live restore passed.
