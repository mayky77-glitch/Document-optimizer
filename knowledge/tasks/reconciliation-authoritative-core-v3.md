---
type: orda_task
status: frozen
orda_status: frozen_contract_pending_planning_commit
card_id: reconciliation-authoritative-core-v3
card_path: knowledge/tasks/reconciliation-authoritative-core-v3.md
version: 1
supersedes: null
work_id: reconciliation-authoritative-core-v3
task_id: reconciliation-authoritative-core-v3
purpose: Add global multi-source selection and aggregated authoritative calculation while preserving legacy single-source behavior.
role: developer
owner: reconciliation-authoritative-core-developer
profile: L2
routing_grade: P4
routing_reason: Multi-file matching, calculation, quality-control and execution contracts require difficult backward-compatible integration.
reasoning_effort: high
assigned_model: gpt-5.6-terra
launch_status: planned
planning_parent_sha: 03ecf3196e207378b0b1d4648c8c07bb5ffe6687
base_sha_source: exact planning commit supplied by Gate 0 launch envelope
dependency_shas:
  - 03ecf3196e207378b0b1d4648c8c07bb5ffe6687
branch: codex/reconciliation-authoritative-core-v3
branch_base_source: exact planning commit supplied by Gate 0 launch envelope
write_scope:
  - src/report_processor/reconciliation_review/__init__.py
  - src/report_processor/reconciliation_review/models.py
  - src/report_processor/reconciliation_review/feedback.py
  - src/report_processor/reconciliation_review/overrides.py
  - src/report_processor/reconciliation_review/pipeline.py
  - src/report_processor/matching/models.py
  - src/report_processor/calculation/engine.py
  - src/report_processor/calculation/__init__.py
  - src/report_processor/quality_control/engine.py
  - src/report_processor/quality_control/checks.py
  - src/report_processor/processing/reconciliation.py
  - src/report_processor/processing/__init__.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/admin_panel/assets
  - src/report_processor/excel_writer
  - tests
  - knowledge/maps
contract_versions:
  input: ReconciliationGlobalInput-1.0
  output: ReconciliationAuthoritativeCore-1.0
acceptance_commands:
  - .venv/bin/pytest -q tests/unit/matching tests/unit/calculation tests/unit/quality_control tests/unit/processing
  - .venv/bin/ruff check src/report_processor/reconciliation_review src/report_processor/matching src/report_processor/calculation src/report_processor/quality_control src/report_processor/processing
  - .venv/bin/ruff format --check src/report_processor/reconciliation_review src/report_processor/matching src/report_processor/calculation src/report_processor/quality_control src/report_processor/processing
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - domain/document-processing
  - layer/backend
  - risk/high
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-core-v3-gate0|Gate 0]]"
---

# Authoritative global reconciliation core

## Required symbols and behavior

- `MatchResult.selected_candidates` is additive. Legacy
  `selected_candidate` remains valid and supplies a singleton effective
  selection; multi-selection leaves the legacy field empty for fail-safe callers.
- `calculate_matches` accepts optional per-candidate inclusion flags and produces
  one deterministic contribution set and one calculation per target. Omitted
  options retain the old result byte-for-byte where public hashes allow it.
- `apply_match_overrides` resolves controlled target category IDs into effective
  selections. It rejects stale/unknown rows and targets; group decisions fan out,
  row decisions win; rejected rows disappear; `cost_only` uses `(False, True)`.
- Quality control validates effective candidate membership, duplicate source use,
  calculation contributions and target cardinality without weakening legacy checks.
- `execute_reconciliation` inspects the original target once, normalizes all
  source workbooks into one ordered set, matches/calculates/QCs once, and writes
  at most once against the original target. It exposes private artifacts to the
  admin integration layer but never presentation provenance.
- Fix Wave 1 defects in owned reconciliation files: opaque string versions,
  decision-aware state input, row feedback, category field naming, and unanimous
  row resolution. Do not add HTTP, SQLite or browser concerns.

## Handoff

Commit and push the feature branch. Return exact feature SHA, changed paths,
focused command results, compatibility risks and integration order. Frozen card
bytes must remain unchanged; do not merge or force-push after handoff.
