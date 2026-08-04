---
type: task
status: done
work_id: reconciliation-wave5-core-v1
role: worker
agent_role: tester
owner: "wave5-tests"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Freeze public schema, metric arithmetic, all hard gates and isolated oracle adapters"
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: "gpt-5.6-terra"
actual_reasoning_effort: "medium"
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "tests/contract/test_grouping_replay_contract.py"
  - "tests/unit/reconciliation_patterns/test_replay.py"
  - "tests/integration/test_grouping_replay_oracles.py"
source_paths:
  - "tests/contract/test_grouping_replay_contract.py"
  - "tests/unit/reconciliation_patterns/test_replay.py"
  - "tests/integration/test_grouping_replay_oracles.py"
depends_on:
  - "reconciliation-wave5-contract"
tags:
  - "task/tests"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 5 replay tests

## Goal

Freeze schemas/fingerprints, split isolation, arithmetic, repeatability, every
promotion STOP reason, activation binding, privacy and no-wiring boundary.

## Completion evidence

- Changed paths: the three frozen Wave 5 test files.
- Commands and tests run: focused `36 passed`; with authoritative calculation
  and writer tests `44 passed`; Ruff/format passed.
- Result: exact models, tamper checks, threshold boundaries, both-split hard
  gates, lifecycle forgery resistance, Decimal calculation and temporary XLSX
  value/format equivalence covered.
- Risks or follow-up: representative private baseline/holdout remains an owner
  gate and was not uploaded or persisted.

## Handoff

Leave in `review` until independent audit.
