---
type: task
status: done
card_status: frozen
version: 1
work_id: reconciliation-wave9-v1
task_id: shadow-acceptance-report
role: worker
agent_role: developer
owner: wave9-report
profile: L1
routing_grade: P3
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: completed
source_base_sha: b733595caeb243a8d9f8aa3b3bb6c5b3fb623fd9
branch: codex/wave9-shadow-acceptance-report
write_scope:
  - src/report_processor/reconciliation_patterns/acceptance_report.py
  - tests/contract/test_shadow_acceptance_report_contract.py
  - tests/integration/test_shadow_acceptance_report.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/reconciliation_patterns/acceptance.py
  - src/report_processor/reconciliation_patterns/acceptance_runner.py
  - src/report_processor/reconciliation_patterns/replay.py
  - src/report_processor/reconciliation_patterns/pattern_registry.py
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - scripts
depends_on:
  - shadow-acceptance-core
contract_versions:
  input: ReconciliationShadowAcceptance-1.0
  output: ReconciliationShadowAcceptanceReport-1.0
acceptance_commands:
  - uv run pytest -q tests/contract/test_shadow_acceptance_report_contract.py tests/integration/test_shadow_acceptance_report.py
---

# Wave 9 safe aggregate report

Serialize only the accepted controlled aggregate to canonical deterministic
JSON. Reject raw terms, workbook paths/names, cell coordinates, rows, formulas,
vectors, model output and backend error text. Write through a symlink-safe
atomic mode-`0600` boundary outside Git; fail closed on unsafe parents,
pre-existing outputs without explicit overwrite or malformed DTOs.

The report is evidence only. It cannot produce activation metadata, owner
approval, registry events, review decisions or workbook output.
