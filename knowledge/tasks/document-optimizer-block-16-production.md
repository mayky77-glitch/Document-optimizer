---
type: task
card_id: document-optimizer-block-16-production
status: draft
version: 1
supersedes: null
work_id: document-optimizer-block-16
task_id: block-16-production
purpose: "Реализовать append-only audit journal, redacted reports, deterministic exports, recovery и feedback lifecycle"
role: worker
agent_role: developer
owner: "block-16-production"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Append-only SQLite hash chain, crash-safe exports, strict allowlist redaction and feedback activation require difficult multi-file implementation."
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
card_path: knowledge/tasks/document-optimizer-block-16-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 375c0a844cf860ca276980a8701e477f0572fca8
branch: codex/block-16-audit-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block16-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "src/report_processor/audit"
source_paths:
  - "src/report_processor/audit"
depends_on: []
forbidden_paths:
  - src/report_processor/__init__.py
  - src/report_processor/cli.py
  - src/report_processor/workflow.py
  - src/report_processor/analytics
  - src/report_processor/business_rules
  - src/report_processor/calculation
  - src/report_processor/domain
  - src/report_processor/excel
  - src/report_processor/excel_writer
  - src/report_processor/extraction
  - src/report_processor/indexing
  - src/report_processor/matching
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
  event: AuditEventEnvelope-16.0
  journal: StageJournal-16.0
  bundle: AuditBundle-16.0
  run_report: RunReport-16.0
  trace_report: TraceReport-16.0
  feedback: FeedbackRuleVersion-16.0
  export_allowlist: AuditExportAllowlist-16.0
  sqlite: AuditSQLite-1
  identity: AuditIdentity-16.0
  workbook_adapter: WorkbookSchemaAdapter-16.0
acceptance_commands:
  - "uv run --extra dev ruff check src/report_processor/audit"
  - "uv run --extra dev ruff format --check src/report_processor/audit"
  - "uv run python -m compileall -q src/report_processor/audit"
tags:
  - "task/implementation"
  - "status/in-progress"
  - "layer/backend"
  - "risk/high"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Block 16 audit production

## Goal

Создать Block 16 строго по frozen manifest. SQLite hash chain и transition
validation выполняются транзакционно. Corrections только новыми events.

## Scope and instructions

- Modify only `write_scope` paths.
- Strict export allowlist. Не хранить и не экспортировать raw document content.
- Deterministic snapshot exports: JSON, JSONL, CSV; fsync, reopen, validate,
  hard-link no-clobber publication.
- Feedback не активируется до `EXPORT_VERIFIED`.
- WorkbookSchema читать только через `WorkbookSchemaAdapter-16.0`; Block 5 не менять.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
