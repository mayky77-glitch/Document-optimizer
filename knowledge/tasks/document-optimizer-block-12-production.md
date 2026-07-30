---
type: task
card_id: document-optimizer-block-12-production
status: done
version: 1
supersedes: null
work_id: document-optimizer-block-12
task_id: block-12-production
purpose: "Реализовать детерминированный matching engine без расчётов и записи"
role: worker
agent_role: developer
owner: block-12-production
profile: L1
routing_grade: P3
progress_revision: 5
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Frozen standalone matching package with deterministic strategy cascade."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
card_path: knowledge/tasks/document-optimizer-block-12-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 2374e8a40aa34291e765e7f072ee4fc733bb5f4c
branch: codex/block-12-matching-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-duckdb"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/matching
source_paths:
  - src/report_processor/matching
depends_on: []
forbidden_paths:
  - src/report_processor/analytics
  - src/report_processor/normalization
  - src/report_processor/target_report
  - src/report_processor/business_rules
  - src/report_processor/storage
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
  public_api: MatchingEngine-12.0
  contract: MatchingContract-12.0
  source_input: NormalizedSourceRow-8.0
  target_input: TargetReportRow-9.0
  rules_input: ValidatedRuleSet-10.0
  output: MatchResult-12.0
acceptance_commands:
  - "uv run --extra dev ruff check src/report_processor/matching"
  - "uv run python -m compileall -q src/report_processor/matching"
  - "uv run --extra dev pytest tests/unit/matching tests/contract/test_block12_matching_contract.py tests/integration/test_block12_matching_engine.py"
tags:
  - task/implementation
  - status/done
  - layer/domain
  - risk/medium
---

# Block 12 production

Создать отдельный `matching` package. Публичный API:
`match_rows(source_rows, target_rows, rule_set, *, target_source_id,
target_fingerprint, policy=MatchingPolicy())`. Реализовать семь frozen
стратегий в заданном порядке. Все значения target нормализовать существующими
data-only normalizers, source document index извлекать только существующим
детерминированным identifier API.

Один source-target pair хранить один раз со всеми сработавшими стратегиями.
Победитель определяется только ordinal стратегии. Confidence — `Decimal` и
объяснение, не tie-breaker. Multiple best, REVIEW и fuzzy не имеют selected
candidate. EXCLUDE сохраняется как blocker и не выбирается. Сохранять полную
source/target provenance. Не вычислять количество/стоимость, не писать Excel,
DuckDB или конфигурацию.
