---
type: task
status: draft
card_status: frozen
version: 1
work_id: reconciliation-wave9-v1
task_id: final-audit
role: auditor
agent_role: reviewer
owner: wave9-audit
profile: L3
routing_grade: P6
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: planned
source_base_sha: b733595caeb243a8d9f8aa3b3bb6c5b3fb623fd9
branch: codex/wave9-final-audit
write_scope: []
depends_on:
  - shadow-acceptance-runner
  - shadow-acceptance-report
contract_versions:
  input: ReconciliationShadowAcceptanceReport-1.0
  output: audit-only
acceptance_commands:
  - uv run pytest -q tests/contract/test_shadow_acceptance_contract.py tests/unit/reconciliation_patterns/test_acceptance.py tests/integration/test_shadow_acceptance_runner.py tests/contract/test_shadow_acceptance_report_contract.py tests/integration/test_shadow_acceptance_report.py
---

# Wave 9 final audit

Read-only P6 review of privacy closure, exact cross-layer binding, fail-closed
status semantics, hard and owner threshold enforcement, source immutability,
calculation/XLSX equivalence, Qdrant-outage isolation, deterministic reporting,
safe persistence and absence of activation/runtime wiring. Reject any path that
can report `PASS` with missing evidence or mutate registry, review state,
workbooks, production routes or external services.
