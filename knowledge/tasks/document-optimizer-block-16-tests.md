---
type: task
card_id: document-optimizer-block-16-tests
status: draft
version: 1
supersedes: null
work_id: document-optimizer-block-16
task_id: block-16-tests
purpose: "Проверить audit contracts, journal integrity, exports, recovery, feedback, real XLSX и performance"
role: worker
agent_role: tester
owner: "block-16-tests"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Concurrency, crash-point, tamper, deterministic export, feedback drift, real-data and performance validation require difficult test design."
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
card_path: knowledge/tasks/document-optimizer-block-16-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 375c0a844cf860ca276980a8701e477f0572fca8
branch: codex/block-16-audit-tests
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block16-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - "tests/unit/audit"
  - "tests/fixtures/audit"
  - "tests/contract/test_block16_audit_contract.py"
  - "tests/integration/test_block16_audit_journal.py"
  - "tests/integration/test_block16_audit_exports.py"
  - "tests/integration/test_block16_cross_store_recovery.py"
  - "tests/integration/test_block16_feedback.py"
  - "tests/integration/test_block16_real_data.py"
  - "tests/integration/test_block16_performance.py"
source_paths:
  - "tests/unit/audit"
  - "tests/fixtures/audit"
  - "tests/contract/test_block16_audit_contract.py"
  - "tests/integration/test_block16_audit_journal.py"
  - "tests/integration/test_block16_audit_exports.py"
  - "tests/integration/test_block16_cross_store_recovery.py"
  - "tests/integration/test_block16_feedback.py"
  - "tests/integration/test_block16_real_data.py"
  - "tests/integration/test_block16_performance.py"
depends_on: []
forbidden_paths:
  - src
  - README.md
  - docs
  - tests/conftest.py
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
acceptance_commands:
  - "uv run --extra dev ruff check tests/unit/audit tests/contract/test_block16_audit_contract.py tests/integration/test_block16_*.py"
  - "uv run --extra dev ruff format --check tests/unit/audit tests/contract/test_block16_audit_contract.py tests/integration/test_block16_*.py"
  - "uv run --extra dev pytest -q tests/unit/audit tests/contract/test_block16_audit_contract.py tests/integration/test_block16_audit_journal.py tests/integration/test_block16_audit_exports.py tests/integration/test_block16_cross_store_recovery.py tests/integration/test_block16_feedback.py"
  - "RUN_SLOW=1 uv run --extra dev pytest -q tests/integration/test_block16_performance.py"
tags:
  - "task/implementation"
  - "status/in-progress"
  - "layer/backend"
  - "risk/high"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Block 16 audit tests

## Goal

Создать black-box tests по frozen manifest независимо от production stream.
До merge допускается ожидаемая ошибка import; после merge весь focused set обязан пройти.

## Scope and instructions

- Modify only `write_scope` paths.
- Reverse-order determinism, tamper, crash points, races, no-clobber, cleanup,
  feedback drift/compaction и cross-store recovery обязательны.
- Real files только read-only через environment path; output только private temp.
- Leak-canary scan не печатает исходное содержимое.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until orchestration accepts the result.
