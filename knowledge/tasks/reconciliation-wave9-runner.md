---
type: task
status: draft
card_status: frozen
version: 1
work_id: reconciliation-wave9-v1
task_id: shadow-acceptance-runner
role: worker
agent_role: developer
owner: wave9-runner
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
source_base_sha: b733595caeb243a8d9f8aa3b3bb6c5b3fb623fd9
branch: codex/wave9-shadow-acceptance-runner
write_scope:
  - src/report_processor/reconciliation_patterns/acceptance_runner.py
  - tests/integration/test_shadow_acceptance_runner.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/reconciliation_patterns/acceptance.py
  - src/report_processor/reconciliation_patterns/replay.py
  - src/report_processor/reconciliation_patterns/pattern_registry.py
  - src/report_processor/reconciliation_patterns/pattern_persistence.py
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - scripts
depends_on:
  - shadow-acceptance-core
contract_versions:
  input: GroupingReplay-1.0
  output: ReconciliationShadowAcceptance-1.0
acceptance_commands:
  - uv run pytest -q tests/integration/test_shadow_acceptance_runner.py
---

# Wave 9 offline acceptance runner

Build an injected, offline-only coordinator that binds sealed disjoint split
identities, existing replay reports and promotion decisions, retrieval and
operational observations, source before/after fingerprints and a Qdrant-outage
decision-delta oracle into the core evaluator. It must not read paths directly,
register a route or CLI, mutate sources, write XLSX, contact Qdrant, promote a
pattern or call production runtime.

Tests prove exact binding, dependency unavailability, source immutability,
calculation/XLSX mismatch propagation, outage zero-delta and deterministic
repeat behavior with injected synthetic collaborators.
