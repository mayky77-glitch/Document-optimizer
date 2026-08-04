---
type: task
status: done
work_id: reconciliation-wave3-quantity-privacy-v1
role: worker
agent_role: developer
owner: "wave3-quantity-privacy"
profile: L2
routing_grade: P4
progress_revision: 2
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "P6 isolated one candidate privacy leak requiring miner and exact regression change"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "src/report_processor/reconciliation_patterns/offline.py"
  - "tests/unit/reconciliation_patterns/test_offline.py"
source_paths:
  - "src/report_processor/reconciliation_patterns/offline.py"
  - "tests/unit/reconciliation_patterns/test_offline.py"
depends_on:
  - "reconciliation-wave3-closure-audit"
tags:
  - "task/implementation"
  - "status/review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 quantity privacy closure

## Goal

Prevent supported include/exclude candidates from serializing raw quantity
fragments while preserving deterministic miner/evaluator behavior.

## Scope and instructions

- Modify only `write_scope` paths.
- Use privacy-safe predicate projection or skip unsafe candidate consistently.
- Add two-document-per-fragment regression and require successful private write.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `src/report_processor/reconciliation_patterns/offline.py`
  - `tests/unit/reconciliation_patterns/test_offline.py`
- Commands and tests run:
  - `.venv/bin/ruff format --check` and `.venv/bin/ruff check` on assigned
    paths: passed.
  - Focused Wave 3 suite: `37 passed`.
  - Combined Wave 3 and work-semantics/grouping/review regression suite:
    `159 passed`.
- Result:
  - Miner now skips slot-template and include/exclude candidates whose skeleton
    itself is a private raw value. Safe typed skeletons retain opaque slot
    signatures and parameter-near profiling remains unchanged.
  - New two-document-per-parameter regression proves `3x10`/`4x16` never occur
    in candidate JSON and `write_candidates` succeeds without weakening the
    writer privacy guard.
  - Bare parameter forms with no typed slots now receive a privacy-safe near
    pair through salted opaque parameter signatures; no raw dimensions are
    serialized.
  - Independent P6 replay accepted the exact 2+2 corpus, canonical bytes and
    mode-0600 output.
- Risks or follow-up:
  - An unsafe predicate is intentionally suppressed rather than projected into
    a broader rule, preserving the frozen conservative mining boundary.

## Handoff

Leave this card in `review` until orchestration accepts the result.
