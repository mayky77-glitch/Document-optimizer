---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave7-v1
task_id: final-audit
role: auditor
agent_role: reviewer
owner: wave7-audit
profile: L3
routing_grade: P6
routing_reason: "Final correctness, privacy, authority and regression audit"
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-sol
actual_reasoning_effort: high
source_base_sha: f2d63d82705e10c191ab67e8a756301ebc7e1ff2
write_scope: []
depends_on:
  - package-optimizer
tags:
  - task/audit
  - status/done
---

# Wave 7 final audit

Read-only P6 audit after all three feature tasks are integrated. Verify contract
invariants, complete-linkage behavior, cannot-link and outlier handling,
optimizer bounds, deterministic IDs/order, privacy, absence of runtime wiring,
focused/regression checks and no test gaming.
