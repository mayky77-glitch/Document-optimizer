---
type: task
card_id: document-optimizer-block-13-production
status: done
version: 1
supersedes: null
work_id: document-optimizer-block-13
task_id: block-13-production
purpose: "Реализовать детерминированный Decimal calculation engine"
role: worker
agent_role: developer
owner: block-13-production
profile: L1
routing_grade: P3
progress_revision: 5
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Frozen standalone calculation package with focused Decimal and rule semantics."
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
card_path: knowledge/tasks/document-optimizer-block-13-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - 60df82430d430ff865ebfe6677ec974dd3b734e2
branch: codex/block-13-calculation-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block13-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/calculation
source_paths:
  - src/report_processor/calculation
depends_on: []
forbidden_paths:
  - src/report_processor/business_rules
  - src/report_processor/matching
  - src/report_processor/normalization
  - src/report_processor/target_report
  - src/report_processor/analytics
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
  public_api: CalculationEngine-13.0
  contract: CalculationContract-13.0
  matching_input: MatchingContract-12.0
  rules_input: ValidatedRuleSet-10.0
  result_output: CalculationResult-13.0
  trace_output: CalculationTrace-13.0
acceptance_commands:
  - "uv run --extra dev ruff check src/report_processor/calculation"
  - "uv run --extra dev ruff format --check src/report_processor/calculation"
  - "uv run python -m compileall -q src/report_processor/calculation"
tags:
  - task/implementation
  - status/claimed
  - layer/domain
  - risk/high
---

# Block 13 production

Создать отдельный `calculation` package и публичный API
`calculate_matches(match_results, rule_set)`.

Считать только `MATCHED.selected_candidate`. `AMBIGUOUS` возвращает
`MANUAL_REVIEW`, `UNMATCHED` — `NO_MATCH`; totals в обоих случаях `None`.
Использовать только конечные `Decimal`, `period_quantity`, `period_cost`,
`default_run_coefficient`, `rounding_quantum` и `ROUND_HALF_UP`. Сначала
агрегировать, затем округлять один раз. Отрицательные корректировки сохранять
со знаком и warning; не clamp и не drop.

Approved rules only. `EXCLUDE` сильнее INCLUDE, `REVIEW` запрещает расчёт,
`include_quantity` и `include_cost` независимы. Пустой `allowed_units` не
ограничивает; конвертация единиц запрещена. Категории определять только по
явному canonical `cost_type_code`; неизвестные значения — `UNCLASSIFIED`,
без анализа work name.

Публиковать immutable `CalculationResult`, `CalculationTrace`,
`CalculationContribution`, category totals, formula tokens, raw/included
значения, rule IDs, решения, warnings и provenance обеих сторон.
Детерминированные SHA-256 IDs и порядок обязательны. Никакой записи Excel,
DuckDB, CLI wiring или исполняемой конфигурации.
