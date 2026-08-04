---
type: task
status: draft
card_status: frozen
version: 1
work_id: reconciliation-wave9-p6-recovery-v1
task_id: recovery-audit
role: auditor
agent_role: reviewer
branch: codex/wave9-p6-audit
source_base_sha: 0b73f3e99c29e567eac4a259e80cc3859dee1660
write_scope: []
depends_on:
  - core-runner-recovery
  - report-boundary-recovery
---

# Wave 9 P6 recovery audit

Read-only re-audit all five findings. Reproduce forged evaluator, self-sealed
missing-evidence `PASS`, one-field replay/provenance mismatches, tampered nested
DTOs, boundary+1 counts/ratios/reasons/payload, truthy non-bool overwrite,
ancestor symlink and directory swap. Confirm no activation/runtime effects.
Accept only with zero HIGH and zero MEDIUM findings.
