---
type: task
status: frozen
orda_status: frozen-wave-2
card_id: qdrant-dense-rag-app
version: 1
supersedes: null
work_id: qdrant-dense-rag-2026-08
task_id: app-integration
purpose: Inject filtered Dense RAG into drawing-card matching while preserving exact feedback precedence and manual review.
role: worker
agent_role: developer
owner: "qdrant-dense-app"
card_path: knowledge/tasks/qdrant-dense-rag-app.md
card_commit_sha_ref: launch-envelope
base_sha_ref: wave-1-integration-sha
dependency_shas_ref:
  - wave-1-integration-sha
branch: codex/qdrant-dense-app
branch_base_sha_ref: wave-1-integration-sha
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-qdrant-dense-app"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Consequential integration must preserve exact feedback priority and manual-review-only behavior."
luna_benchmark_evidence: ""
exception_evidence: ""
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
  - "src/report_processor/drawing_card/matching/semantic.py"
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "tests/unit/drawing_card/test_matcher_dictionary.py"
  - "tests/integration/test_dense_rag_drawing_card.py"
source_paths:
  - "src/report_processor/drawing_card/matching/semantic.py"
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "tests/unit/drawing_card/test_matcher_dictionary.py"
  - "tests/integration/test_dense_rag_drawing_card.py"
depends_on:
  - "qdrant-dense-rag-core"
forbidden_paths:
  - "src/report_processor/stage_rag"
  - "src/report_processor/drawing_card/review"
  - "src/report_processor/admin_panel"
  - "tests/unit/stage_rag"
  - "tests/fixtures"
  - "pyproject.toml"
  - "uv.lock"
  - "knowledge"
contract_versions:
  input: DenseRetriever-1.0+ReviewFeedbackStore-1.0
  output: DrawingCardDenseRAG-1.0
acceptance_commands:
  - "uv run pytest -q tests/unit/drawing_card/test_matcher_dictionary.py tests/integration/test_dense_rag_drawing_card.py"
  - "uv run ruff check src/report_processor/drawing_card/matching/semantic.py src/report_processor/drawing_card/matching/matcher.py tests/unit/drawing_card/test_matcher_dictionary.py tests/integration/test_dense_rag_drawing_card.py"
  - "uv run ruff format --check src/report_processor/drawing_card/matching/semantic.py src/report_processor/drawing_card/matching/matcher.py tests/unit/drawing_card/test_matcher_dictionary.py tests/integration/test_dense_rag_drawing_card.py"
  - "git diff --check"
tags:
  - "task/implementation"
  - "status/in-progress"
  - "domain/rag"
  - "layer/backend"
  - "risk/high"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Drawing-card Dense RAG injection and safe fallback

## Goal

Add an injectable Dense Retriever path with explicit tenant/project/document and
taxonomy context. Default remains local deterministic compatibility behavior.
Exact review feedback, deterministic rules and exclusions run first. Semantic
candidates only enrich unresolved review, expose bounded candidate IDs/scores,
and never change quantity, cost or category automatically. Timeout/unavailable
returns controlled manual review/fallback without leaking backend details.

## Scope and instructions

- Modify only `write_scope` paths.
- Do not enable a global tenant, production endpoint or admin workflow default.
- Tests must prove cross-tenant candidates cannot enter evidence and score never auto-applies.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
