---
type: task
status: frozen
orda_status: frozen
card_id: qdrant-dense-rag-infra
version: 1
supersedes: null
work_id: qdrant-dense-rag-2026-08-v2
task_id: local-infra
purpose: Build a bounded local embedding HTTP service and reproducible Qdrant dev/test operations without committed secrets.
role: worker
agent_role: devops
owner: "qdrant-dense-infra"
card_path: knowledge/tasks/qdrant-dense-rag-infra.md
card_commit_sha_ref: launch-envelope
base_sha_ref: published-base-sha
dependency_shas_ref:
  - published-base-sha
branch: codex/qdrant-dense-infra
branch_base_sha_ref: published-base-sha
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-qdrant-dense-infra"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded local service, Docker Compose, snapshot scripts and runbook with no production access."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - "src/report_processor/stage_rag/service.py"
  - "tests/unit/stage_rag/test_embedding_service.py"
  - "deploy/qdrant"
  - "compose.qdrant.yml"
  - "Dockerfile.embedding"
  - "docs/qdrant-dense-rag-runbook.md"
source_paths:
  - "src/report_processor/stage_rag/service.py"
  - "tests/unit/stage_rag/test_embedding_service.py"
  - "deploy/qdrant"
  - "compose.qdrant.yml"
  - "Dockerfile.embedding"
  - "docs/qdrant-dense-rag-runbook.md"
depends_on: []
forbidden_paths:
  - "src/report_processor/stage_rag/__init__.py"
  - "src/report_processor/stage_rag/encoder.py"
  - "src/report_processor/stage_rag/retrieval.py"
  - "src/report_processor/stage_rag/models.py"
  - "src/report_processor/drawing_card"
  - "pyproject.toml"
  - "uv.lock"
  - "knowledge"
  - ".github"
contract_versions:
  input: StageEncoder-18.0
  output: LocalEmbeddingService-1.0
  qdrant: Qdrant-REST-1.18
acceptance_commands:
  - "uv run pytest -q tests/unit/stage_rag/test_embedding_service.py"
  - "uv run ruff check src/report_processor/stage_rag/service.py tests/unit/stage_rag/test_embedding_service.py"
  - "uv run ruff format --check src/report_processor/stage_rag/service.py tests/unit/stage_rag/test_embedding_service.py"
  - "QDRANT_API_KEY=test-only-key docker compose -f compose.qdrant.yml config --quiet"
  - "bash -n deploy/qdrant/scripts/create-collection.sh deploy/qdrant/scripts/snapshot.sh deploy/qdrant/scripts/restore-check.sh"
  - "git diff --check"
tags:
  - "task/implementation"
  - "status/in-progress"
  - "domain/rag"
  - "layer/infra"
  - "risk/high"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Local embedding service and Qdrant dev operations

## Goal

Expose pinned local RuBERT embeddings through a bounded Starlette service with
health and OpenAI-compatible embeddings endpoints. Reject oversized batches and
texts, never log source text, and return controlled unavailable errors. Provide
Qdrant 1.18.3 Compose, persistent volume, loopback dev exposure, required API-key
environment, healthcheck, resource limits, collection/snapshot/restore scripts
and a no-secret runbook. No real server access or production deployment.

## Scope and instructions

- Modify only `write_scope` paths.
- Docker image/model cache must be pinned or externally mounted; no remote model download.
- Scripts must be idempotent, `set -euo pipefail`, bounded by explicit URLs and refuse missing keys.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
