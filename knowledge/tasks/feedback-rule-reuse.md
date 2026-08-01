---
type: task
status: done
work_id: drawing-card-million-values-v3
role: worker
agent_role: developer
owner: "feedback-rule-developer"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Existing exact-feedback interface needs deterministic priority"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-01
updated: 2026-08-01
write_scope:
  - "src/report_processor/drawing_card/review/inline.py"
  - "src/report_processor/drawing_card/matching/examples.py"
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "src/report_processor/drawing_card/workflow.py"
  - "src/report_processor/admin_panel/drawing_card_service.py"
source_paths:
  - "src/report_processor/drawing_card/review/inline.py"
  - "src/report_processor/drawing_card/matching/examples.py"
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "src/report_processor/drawing_card/workflow.py"
  - "src/report_processor/admin_panel/drawing_card_service.py"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
  - "drawing-card"
  - "rag"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Повторное применение решений без новых карточек

## Goal

Reuse the latest exact local review decision before RAG so approve, reject, category change, and cost-only choices do not produce the same review card again. Keep private row names out of repository resources and knowledge.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `src/report_processor/drawing_card/review/inline.py`
  - `src/report_processor/drawing_card/matching/examples.py`
  - `src/report_processor/drawing_card/matching/matcher.py`
- Commands and tests run:
  - `uv run ruff check src/report_processor/drawing_card/review/inline.py src/report_processor/drawing_card/matching/examples.py src/report_processor/drawing_card/matching/matcher.py`
  - `uv run pytest tests/unit/drawing_card/test_inline_review_flow.py -q` — 5 passed
  - Isolated temporary feedback replay: approve → reject produces one JSONL record and exact exclude decision.
  - `git diff --check`
- Result:
  - Feedback rule identity is normalized name plus unit; a later explicit decision replaces earlier action-specific feedback.
  - Legacy duplicate local feedback is compacted on load with latest JSONL decision winning; local feedback also overrides a bundled exact example.
  - `skip` is persisted as an exact exclude rule, and exact local decisions are evaluated before formula/no-impact guards and all RAG paths.
- Risks or follow-up:
  - Unit remains part of exact identity by design; same wording with another known unit still needs an independent decision.

## Proposed knowledge delta

- Record that `review-feedback.jsonl` is a private, latest-write-wins rule store keyed by normalized work name and unit; it is applied before retrieval/RAG and never copied into repository resources.

## Handoff

Leave this card in `review` until orchestration accepts the result.
