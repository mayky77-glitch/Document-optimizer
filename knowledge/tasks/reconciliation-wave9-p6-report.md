---
type: task
status: done
card_status: frozen
version: 1
work_id: reconciliation-wave9-p6-recovery-v1
task_id: report-boundary-recovery
role: worker
agent_role: developer
branch: codex/wave9-p6-report
source_base_sha: 0b73f3e99c29e567eac4a259e80cc3859dee1660
write_scope:
  - src/report_processor/reconciliation_patterns/acceptance_report.py
  - tests/contract/test_shadow_acceptance_report_contract.py
  - tests/integration/test_shadow_acceptance_report.py
forbidden_paths:
  - src/report_processor/reconciliation_patterns/acceptance.py
  - src/report_processor/reconciliation_patterns/acceptance_runner.py
  - src/report_processor/reconciliation_patterns/replay.py
  - src/report_processor/admin_panel
  - src/report_processor/calculation
  - src/report_processor/excel_writer
---

# Wave 9 P6 report boundary recovery

Red-first close ancestor-symlink/TOCTOU and overwrite/bounds findings. Open the
absolute parent component-by-component with stable directory descriptors and
`O_DIRECTORY|O_NOFOLLOW`; reject dot segments, symlink/non-directory
components and any stable ancestor containing `.git`. Never reopen the full
parent path after validation. Add ancestor-symlink and swap-race regression
tests proving no publication inside Git.

Require `type(overwrite) is bool`, cap serialized payload size and reject any
decision that violates the strengthened core `PASS` binding invariant. Preserve
canonical bytes, atomic replace, file and directory fsync and mode `0600`.
