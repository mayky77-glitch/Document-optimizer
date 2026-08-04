---
type: task
status: superseded
work_id: reconciliation-wave3-v1
role: worker
agent_role: developer
owner: "wave3-core"
profile: L2
routing_grade: P4
progress_revision: 3
state_fingerprint: "wave3-core-public-contract-recovery-v1"
no_progress_count: 0
circuit_state: closed
routing_reason: "Multi-schema deterministic offline implementation maps to P4."
luna_benchmark_evidence: ""
exception_evidence: ""
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
  - src/report_processor/reconciliation_patterns/__init__.py
  - src/report_processor/reconciliation_patterns/offline.py
  - scripts/profile_reconciliation_corpus.py
  - scripts/mine_reconciliation_patterns.py
  - scripts/evaluate_reconciliation_patterns.py
source_paths:
  - knowledge/tasks/reconciliation-wave3-contract.md
  - src/report_processor/work_semantics
  - src/report_processor/analytics/serialization.py
depends_on:
  - reconciliation-wave3-contract
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 offline profiler/miner/evaluator core

## Goal

Implement the frozen Wave 3 pure core and three thin privacy-safe CLI adapters.

## Scope and instructions

- Modify only `write_scope` paths; do not edit tests, config or legacy modules.
- Follow the frozen contract exactly, including strict schemas, confirmed-only
  support, dedup, seven candidate kinds, descriptive evaluator and safe writes.
- No network, AI, Qdrant, openpyxl, legacy integration or Git operations.
- Leave status `review` with exact evidence.

## Completion evidence

- Changed paths: `src/report_processor/reconciliation_patterns/__init__.py`,
  `src/report_processor/reconciliation_patterns/offline.py`, and three
  `scripts/*reconciliation*` CLI adapters.
- Commands and tests run: `.venv/bin/ruff format --check`; `.venv/bin/ruff
  check`; focused Wave 3 unit/contract suites (`16 passed`); Wave 1/2
  work-semantics unit and contract suites (`102 passed`).
- Result: public frozen candidate contract is now explicit: exact
  `CandidateKind`, controlled six-field `PatternScope`, exact support counts,
  candidate record/payload fields and exact descriptive evaluator counts with
  rational agreement. Private predicates remain in proposals. Critical
  modifiers use the one-uncovered-token partition without lexical-near gating.
- Risks or follow-up: no trusted post-apply corpus exporter is part of this
  wave; no further known Wave 3 contract failures in focused evidence.

## Handoff

Leave this card in `review` until orchestration accepts the result.
