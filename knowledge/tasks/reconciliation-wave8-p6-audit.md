---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave8-p6-recovery-v1
task_id: recovery-audit
role: auditor
agent_role: reviewer
branch: codex/wave8-p6-audit
write_scope: []
depends_on:
  - ui-behavior-recovery
---

# Wave 8 P6 recovery audit

Read-only re-audit of the six original findings and inert-boundary guarantees.
Reject recovery if cross-layer DTOs diverge, privacy closure is not exact, CAS
can lose an intent, persisted intents are not rebound, UI tests remain static
only, focus is not identity-stable, or runtime behavior becomes active.
