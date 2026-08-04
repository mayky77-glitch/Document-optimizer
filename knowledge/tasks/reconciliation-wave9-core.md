---
type: task
status: done
card_status: frozen
version: 1
work_id: reconciliation-wave9-v1
task_id: shadow-acceptance-core
role: worker
agent_role: developer
owner: wave9-core
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: completed
source_base_sha: b733595caeb243a8d9f8aa3b3bb6c5b3fb623fd9
branch: codex/wave9-shadow-acceptance-core
write_scope:
  - src/report_processor/reconciliation_patterns/acceptance.py
  - tests/contract/test_shadow_acceptance_contract.py
  - tests/unit/reconciliation_patterns/test_acceptance.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/reconciliation_patterns/replay.py
  - src/report_processor/reconciliation_patterns/pattern_registry.py
  - src/report_processor/reconciliation_patterns/pattern_persistence.py
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - scripts
depends_on:
  - reconciliation-wave8-v1
contract_versions:
  input: GroupingReplay-1.0
  output: ReconciliationShadowAcceptance-1.0
acceptance_commands:
  - uv run pytest -q tests/contract/test_shadow_acceptance_contract.py tests/unit/reconciliation_patterns/test_acceptance.py
---

# Wave 9 shadow acceptance core

Define frozen controlled aggregate DTOs and a pure fail-closed evaluator over
existing replay, promotion and operational evidence. Preserve the plan's hard
group/action, coverage, contradiction, equivalence, outage, immutability and
repeatability gates. Owner-defined retrieval, reuse, correction, suspension,
latency, index and availability thresholds are mandatory for `PASS`; absence
returns `BLOCKED`.

Only controlled codes, bounded integers, exact ratios and salted opaque refs
may cross the boundary. Status is `PASS`, `FAIL`, `BLOCKED` or `UNAVAILABLE`.
Do not create activation metadata or import runtime, registry persistence,
review, calculation, writer, workbook or Qdrant clients.
