---
type: orchestration
status: frozen
orda_status: gate_pending_planning_commit
work_id: reconciliation-authoritative-core-v3
objective: Add backward-compatible global multi-source matching and calculation contracts required by authoritative reconciliation decisions.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: 03ecf3196e207378b0b1d4648c8c07bb5ffe6687
published_base_sha_source: planning commit containing this manifest and frozen card
wave: 1
max_parallel: 1
max_spawns: 2
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-02T03:52:00+08:00
tags:
  - knowledge/orchestration
  - status/frozen
  - domain/document-processing
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-core-v3]]"
---

# Gate 0: authoritative reconciliation core

## Frozen contract

- Current sequential per-source execution and single selected candidate are not
  authoritative for global groups. This wave adds one global normalized row set,
  effective multi-selection per target, and one aggregated Decimal calculation.
- Legacy single-source matching, calculation, quality-control and processing APIs
  remain behavior-compatible by default.
- Explicit review maps controlled target IDs to selected source rows. Reject adds
  no contribution; `cost_only` contributes cost but no quantity; row decisions
  override group decisions.
- The core returns private calculation artifacts plus safe review inputs. It does
  not own HTTP routes, SQLite persistence, workbook paths in presentation, or UI.
- Keep new executable files below 500 lines; split cohesive helpers before 500.

## Baseline

On parent `03ecf3196e207378b0b1d4648c8c07bb5ffe6687`:

- `.venv/bin/pytest -q tests/unit/matching tests/unit/calculation tests/unit/quality_control tests/unit/processing` — `10 passed`.
- Targeted Ruff check and format-check — passed.
- `git diff --check` — passed.

## Dependency graph

This core feature merges first. A successor ORDA work ID freezes admin/API
wiring against the accepted core merge SHA. Focused authoritative tests are
frozen into that later merge and run in the final test wave.
