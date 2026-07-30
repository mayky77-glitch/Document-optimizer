---
type: task
card_id: document-optimizer-block-14-production
status: claimed
version: 1
supersedes: null
work_id: document-optimizer-block-14
task_id: block-14-production
purpose: "Реализовать детерминированный write gate и QualityControlReport"
role: worker
agent_role: developer
owner: block-14-production
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Frozen standalone quality-control package over accepted Block 10–13 contracts."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/document-optimizer-block-14-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - d8a55a82997d8f97a14f9287a32900f942ea2229
branch: codex/block-14-quality-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block14-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/quality_control
source_paths:
  - src/report_processor/quality_control
depends_on: []
forbidden_paths:
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/business_rules
  - src/report_processor/target_report
  - src/report_processor/normalization
  - src/report_processor/analytics
  - src/report_processor/storage
  - src/report_processor/cli.py
  - src/report_processor/__init__.py
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - .github
  - knowledge
  - "**/*.xlsx"
  - "**/*.xlsm"
contract_versions:
  public_api: QualityControlEngine-14.0
  contract: QualityControlContract-14.0
  matching_input: MatchingContract-12.0
  calculation_input: CalculationContract-13.0
  rules_input: ValidatedRuleSet-10.0
  report_output: QualityControlReport-14.0
acceptance_commands:
  - "uv run --extra dev ruff check src/report_processor/quality_control"
  - "uv run --extra dev ruff format --check src/report_processor/quality_control"
  - "uv run python -m compileall -q src/report_processor/quality_control"
tags:
  - task/implementation
  - status/claimed
  - layer/domain
  - risk/high
---

# Block 14 production

Создать отдельный `quality_control` package и публичный API
`evaluate_quality_control(match_results, calculation_results, rule_set)`.

Не менять модели блоков 10–13. Проверять строгую кардинальность, identities,
trace/category totals, provenance, formula/cache errors, нормализованные units,
quantity/cost consistency и допуск из `rule_set.defaults.cost_tolerance_ratio`.
Пустой target selected cost — допустимая ячейка назначения, а не missing value.

Решения имеют строгий приоритет `BLOCK_WRITE` → `REQUIRE_MANUAL_REVIEW` →
`ALLOW_WRITE_WITH_WARNINGS` → `ALLOW_WRITE`. Использовать только конечные
`Decimal`, без epsilon, float, скрытого округления и unit conversion.

Публиковать immutable models, детерминированные SHA-256 IDs и безопасный
provenance. Не копировать raw cell values, formula text и содержимое документов.
Никакой записи Excel, CLI wiring, DuckDB или бизнес-логики будущих блоков.
