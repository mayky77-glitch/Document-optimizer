---
type: task
card_id: document-optimizer-block-10-production
status: done
version: 1
supersedes: null
work_id: document-optimizer-blocks-09-10
task_id: block-10-production
purpose: "Загрузить и валидировать data-only JSON/YAML бизнес-правила"
role: worker
agent_role: developer
owner: block-10-production
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded validation package with explicit non-executable configuration contract."
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
card_path: knowledge/tasks/document-optimizer-block-10-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - c04008c51d39996788b0bcb9d6465e280d01938c
branch: codex/block-10-business-rules-production
worktree: "/Users/x/Documents/Сооотношение документов/Document-optimizer-block10-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/business_rules
source_paths:
  - src/report_processor/business_rules
depends_on: []
forbidden_paths:
  - src/report_processor/target_report
  - src/report_processor/cli.py
  - src/report_processor/cli_business_rules.py
  - src/report_processor/__init__.py
  - src/report_processor/storage
  - src/report_processor/normalization
  - tests
  - docs
  - README.md
  - pyproject.toml
  - uv.lock
  - knowledge
contract_versions:
  input: business-rules-json-yaml-10.0
  output: "ValidatedRuleSet-10.0 + RuleConfigurationVersion-1.0"
  canonical: business-rules-json-10.0
acceptance_commands:
  - "uv run ruff check src/report_processor/business_rules"
  - "uv run pytest tests/unit/business_rules tests/contract/test_block10_public_contract.py"
tags:
  - task/implementation
  - status/done
  - layer/backend
  - risk/high
---

# Block 10 production

Конфигурация максимум 1 MiB, depth 32, rules 1000. JSON duplicate keys,
unknown keys, YAML tags/aliases/anchors, floats, bool-as-number, NaN/Infinity,
includes, env interpolation, URLs, file references и executable payloads отклонять.
Decimal принимать только plain strings. Canonical bytes — sorted compact UTF-8 JSON.
Проверять versions, conflicts, precedence, source priorities, units,
coefficients и M01–M15 data records. Никаких `eval`, `exec`, imports, templates,
callables и config-defined regex.
