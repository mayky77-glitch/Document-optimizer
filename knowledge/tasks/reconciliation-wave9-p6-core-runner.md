---
type: task
status: done
card_status: frozen
version: 1
work_id: reconciliation-wave9-p6-recovery-v1
task_id: core-runner-recovery
role: worker
agent_role: developer
branch: codex/wave9-p6-core-runner
source_base_sha: 0b73f3e99c29e567eac4a259e80cc3859dee1660
write_scope:
  - src/report_processor/reconciliation_patterns/acceptance.py
  - src/report_processor/reconciliation_patterns/acceptance_runner.py
  - tests/contract/test_shadow_acceptance_contract.py
  - tests/unit/reconciliation_patterns/test_acceptance.py
  - tests/integration/test_shadow_acceptance_runner.py
forbidden_paths:
  - src/report_processor/reconciliation_patterns/acceptance_report.py
  - src/report_processor/reconciliation_patterns/replay.py
  - src/report_processor/reconciliation_patterns/pattern_registry.py
  - src/report_processor/admin_panel
  - src/report_processor/calculation
  - src/report_processor/excel_writer
---

# Wave 9 P6 core and runner recovery

Red-first close forged `PASS`, incomplete provenance, tampered DTO and bounds
findings. `PASS` requires all five evidence fingerprints and the injected
evaluator result must exactly equal a fresh deterministic core evaluation.
Revalidate exact types and seals at every call, including nested replay data.

Bind contradiction and decision-mismatch sums directly; bind threshold corpus
and holdout refs to the sealed snapshots; bind group/action counts to explicit
observation provenance; bind source identities to snapshot manifests/source
sets; bind operational metrics to a sealed authoritative observation and outage
delta to an oracle fingerprint. Define explicit upper bounds for integers,
ratio operands and reason tuples. Add one-field adversarial tests for every
binding, raw post-construction mutation and boundary+1 values. No activation,
runtime, registry, review, workbook or network effects.
