---
type: task
status: draft
card_id: reconciliation-accuracy-final-review
version: 1
work_id: reconciliation-max-accuracy-specialists-v1
task_id: final-review
purpose: Independently synthesize all reconciliation audit evidence and reject overstated accuracy claims.
role: auditor
agent_role: reviewer
owner: final-review
profile: L3
routing_grade: P6
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: planned
source_base_sha_source: exact planning commit supplied in launch envelope
branch: codex/reconciliation-accuracy-final-review
branch_base_sha_source: exact planning commit supplied in launch envelope
write_scope: []
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - "**/*.xlsx"
contract_versions:
  input: ReconciliationAccuracyEvidence-1.0
  output: ReconciliationAccuracyFinalAudit-1.0
acceptance_commands:
  - uv run pytest -q -k reconciliation
tags:
  - task/review
  - status/draft
  - domain/document-processing
  - risk/high
---

# Final P6 reconciliation audit

Read-only synthesis after six specialist reports and root-owned de-identified workbook evidence.
Produce a stage-by-stage pass/fail/unknown matrix, contradictions and blind spots, severity-ranked
material findings and explicit limits on any accuracy claim. No implementation or private-data
inspection belongs in this task.
