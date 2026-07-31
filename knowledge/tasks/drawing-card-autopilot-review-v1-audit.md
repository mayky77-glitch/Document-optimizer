---
type: task
card_id: drawing-card-autopilot-review-v1-audit
status: done
version: 1
work_id: drawing-card-autopilot-review-v1
task_id: audit
purpose: "Проверить финансовую безопасность review autopilot"
role: auditor
agent_role: reviewer
owner: "reviewer"
profile: L3
routing_grade: P6
progress_revision: 1
state_fingerprint: "c9917b63e06fa29bea0d99f2a3f2d2077ba5a468"
no_progress_count: 0
circuit_state: closed
routing_reason: "Consequential financial-category auto-resolution final review"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-sol
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/drawing-card-autopilot-review-v1-audit.md
base_sha_ref: accepted_integration_sha
write_scope: []
source_paths: []
depends_on: []
tags:
  - "task/audit"
  - "status/done"
  - "drawing-card"
  - "review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Drawing card review autopilot audit

## Goal

Audit fail-closed guards, provenance, exact scoping, aggregate invariants and rollback.

## Scope and instructions

- Audit read-only.
- Reject any quantity auto-include across unit mismatch.
- Reject any dependency on RuBERT category/score for activation.
- Require private replay residual actions <= 25 and unchanged aggregate/card totals.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/drawing_card/autopilot/consensus.py`,
  `src/report_processor/drawing_card/matching/matcher.py`, workflow/service wiring,
  and focused unit/service regressions.
- Commands and tests run: `uv run pytest -q` -> 727 passed, 22 skipped;
  Ruff check/format clean; private four-workbook manual-vs-autopilot gold replay.
- Result: `APPROVE`. Review reduced from 719 rows / 254 clusters to
  155 rows / 18 clusters. Manual and autopilot runs have zero business diff
  across 786 aggregates and 23,328 planned writes; 7,776 card rows unchanged;
  source hashes match.
- Risks or follow-up: 18 disputed clusters remain explicitly manual by design.
  Removing private `machine-consensus.jsonl` is the rollback switch.

## Handoff

Accepted after the P1 negative-rule precedence fix and gold replay.
