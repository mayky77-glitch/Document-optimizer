---
type: task
card_id: document-optimizer-block-11-production
status: claimed
version: 1
supersedes: null
work_id: document-optimizer-block-11
task_id: block-11-production
purpose: "Реализовать отдельный воспроизводимый DuckDB analytical store"
role: worker
agent_role: database-engineer
owner: block-11-production
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Schema, transactional loads, deterministic queries and parameterized SQL are a database-specialist scope."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
card_path: knowledge/tasks/document-optimizer-block-11-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 654c3a4c53971f2e9ae617a36f4089315ef26d36
branch: codex/block-11-analytics-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block11-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/analytics
source_paths:
  - src/report_processor/analytics
depends_on: []
forbidden_paths:
  - src/report_processor/storage
  - src/report_processor/normalization
  - src/report_processor/target_report
  - src/report_processor/business_rules
  - src/report_processor/cli.py
  - src/report_processor/__init__.py
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  public_api: AnalyticalStore-11.0
  database_schema: AnalyticalSchema-1
  source_input: "NormalizedSourceRow@654c3a4"
  target_input: TargetReportRow-9.0
  rules_input: ValidatedRuleSet-10.0
acceptance_commands:
  - "uv run ruff check src/report_processor/analytics"
  - "uv run python -m compileall -q src/report_processor/analytics"
  - "uv run pytest tests/unit/analytics tests/contract/test_block11_analytical_contract.py tests/integration/test_block11_analytical_store.py"
tags:
  - task/implementation
  - status/claimed
  - layer/data
  - risk/high
---

# Block 11 production

Создать отдельный `analytics` package и отдельную DuckDB schema. Не менять
совместимый `storage` v1. Публичный API: `AnalyticalStore`, bounded query/load
models и controlled errors. Загрузки source/target/rules выполняются
транзакционно, детерминированно и только параметризованным DML. DDL identifiers
и named queries — фиксированный allowlist. `source_row_id` unique, `line_id`
только индексируемая бизнес-группа. Target loader требует explicit source ID и
fingerprint. Same ID/different payload всегда rollback. Decimal хранить без
float и без неявного округления. Views не содержат matching logic блока 12.
