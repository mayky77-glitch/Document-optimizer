---
type: task
card_id: document-optimizer-block-17-production
status: draft
version: 1
supersedes: null
work_id: document-optimizer-block-17
task_id: block-17-production
purpose: "Реализовать тонкий ProcessingEngine-17.0 и process CLI поверх Blocks 1-16"
role: worker
agent_role: developer
owner: "block-17-production"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Difficult multi-module controller, deterministic resume/cache and safe mode boundaries."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-17-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - ca6300471b52ba1ef80585b3881cb77e04a6be50
branch: codex/block-17-processing-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block17-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "src/report_processor/processing"
  - "src/report_processor/cli_process.py"
source_paths:
  - "src/report_processor/processing"
  - "src/report_processor/cli_process.py"
depends_on: []
forbidden_paths:
  - src/report_processor/__init__.py
  - src/report_processor/cli.py
  - src/report_processor/workflow.py
  - src/report_processor/adapters
  - src/report_processor/analytics
  - src/report_processor/audit
  - src/report_processor/business_rules
  - src/report_processor/calculation
  - src/report_processor/domain
  - src/report_processor/excel
  - src/report_processor/excel_writer
  - src/report_processor/extraction
  - src/report_processor/identifiers
  - src/report_processor/inventory
  - src/report_processor/matching
  - src/report_processor/materialization
  - src/report_processor/metadata
  - src/report_processor/normalization
  - src/report_processor/quality_control
  - src/report_processor/schema
  - src/report_processor/selection
  - src/report_processor/storage
  - src/report_processor/target_report
  - src/report_processor/training_data
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - .gitignore
  - .github
  - knowledge
  - .codex
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  request_result: ProcessingContract-17.0
  engine: ProcessingEngine-17.0
  state: ProcessingState-17.0
acceptance_commands:
  - "uv run --extra dev ruff check src/report_processor/processing src/report_processor/cli_process.py"
  - "uv run --extra dev ruff format --check src/report_processor/processing src/report_processor/cli_process.py"
  - "uv run python -m compileall -q src/report_processor/processing src/report_processor/cli_process.py"
tags:
  - "task/implementation"
  - "status/draft"
  - "layer/backend"
  - "risk/high"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Block 17 production

## Goal

Implement frozen ProcessingContract-17.0. Controller coordinates existing public
APIs; it must not duplicate matching, calculation, QC, writer or audit logic.

## Scope

- Modify only `write_scope`.
- Keep modules cohesive and below the repository hard size limit.
- Preserve deterministic request/bulk order, mode boundaries and no-clobber.
- Leave shared CLI registration and workflow facade to the integration owner.

## Handoff

Commit and push the feature branch. Leave the card for integration-owner updates.
