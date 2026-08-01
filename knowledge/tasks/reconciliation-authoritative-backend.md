---
type: orda_task
status: frozen
card_id: reconciliation-authoritative-backend
version: 1
supersedes: null
work_id: reconciliation-authoritative-classification-v3
task_id: reconciliation-authoritative-backend
purpose: Build isolated authoritative grouping, override, feedback, and safe payload modules without shared HTTP or processing wiring.
role: developer
owner: reconciliation-authoritative-developer
card_path: knowledge/tasks/reconciliation-authoritative-backend.md
card_commit_sha_source: exact planning commit supplied by Gate 0 launch envelope
profile: L2
routing_grade: P4
routing_reason: Cross-component match override, calculation rerun, feedback, and safe API contracts replace journal-only behavior.
reasoning_effort: high
assigned_model: gpt-5.6-terra
launch_status: planned
planning_parent_sha: 3f3b31e4e0aff0905fd0118210817b3425af45d3
base_sha_source: exact planning commit supplied by Gate 0 launch envelope
dependency_shas: []
branch: codex/reconciliation-authoritative-backend-v3
branch_base_source: exact planning commit supplied by Gate 0 launch envelope
write_scope:
  - src/report_processor/reconciliation_review/__init__.py
  - src/report_processor/reconciliation_review/models.py
  - src/report_processor/reconciliation_review/grouping.py
  - src/report_processor/reconciliation_review/feedback.py
  - src/report_processor/reconciliation_review/overrides.py
  - src/report_processor/admin_panel/reconciliation_review_api.py
  - src/report_processor/admin_panel/reconciliation_review_presentation.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/processing/adapters.py
  - src/report_processor/excel_writer/engine.py
  - tests
  - knowledge/maps
contract_versions:
  input: ReconciliationAuthoritativeReviewInput-1.0
  output: ReconciliationAuthoritativeDecision-1.0
acceptance_commands:
  - .venv/bin/ruff check src/report_processor/reconciliation_review src/report_processor/admin_panel/reconciliation_review_api.py src/report_processor/admin_panel/reconciliation_review_presentation.py
  - .venv/bin/ruff format --check src/report_processor/reconciliation_review src/report_processor/admin_panel/reconciliation_review_api.py src/report_processor/admin_panel/reconciliation_review_presentation.py
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
  - layer/backend
  - risk/high
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-classification-v3-gate0|Gate 0]]"
---

# Authoritative reconciliation domain

## Frozen contract

- Category is a controlled target-report row/stage identity, never one of the
  drawing-card category constants.
- Build global groups across all uploaded source rows by normalized work name
  and normalized unit. A conservative common-prefix group is allowed only when
  its shared prefix remains a complete semantic name; empty names are singleton.
- Group/version identity hashes grouping inputs and every sorted member ID.
- One decision carries `accept` or `reject`; accepted decisions carry a target
  category and mode `quantity_cost` or `cost_only`. Row decisions override a
  group decision for that row.
- Override application returns controlled match/calculation inputs. Reject
  excludes both quantity and cost. `cost_only` excludes quantity only.
- Latest feedback is keyed by normalized exact name or accepted group prefix
  plus unit. It contains only controlled category/mode/action fields, is applied
  before review generation, and prevents already resolved groups from recurring.
- Presentation exposes every safe member with display name, unit, quantity and
  cost, formatted to two decimals. Paths, sheets, coordinates, provenance,
  upstream warnings and technical metrics are forbidden.

## Handoff evidence

Move to `review` only with changed paths, feature SHA, Ruff/format/diff-check
results, contract risks, and a proposed integration order. Do not edit shared
wiring and do not merge.
