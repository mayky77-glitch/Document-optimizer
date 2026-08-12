---
type: task
status: draft
card_id: reconciliation-accuracy-ingestion
version: 1
work_id: reconciliation-max-accuracy-specialists-v1
task_id: ingestion-target
purpose: Audit source ingestion and target interpretation for row loss, column drift, indices and formula caches.
role: worker
agent_role: debugger
owner: ingestion-target
profile: L2
routing_grade: P4
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
source_base_sha_source: exact planning commit supplied in launch envelope
branch: codex/reconciliation-accuracy-ingestion
branch_base_sha_source: exact planning commit supplied in launch envelope
write_scope: []
forbidden_paths:
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
  - "**/*.xlsx"
  - "**/*.xlsm"
  - "**/*.xlsb"
contract_versions:
  input: ReconciliationProductionPath-1.0
  output: ReconciliationIngestionAudit-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/admin_panel/test_reconciliation_sources_provenance.py tests/integration/test_reconciliation_authoritative_flow.py
tags:
  - task/review
  - status/draft
  - domain/document-processing
  - layer/data
  - risk/high
---

# Ingestion and target interpretation audit

Read-only audit of reconciliation uploads, source selection/extraction and target row binding.
Prove supported KS-2/KS-6a layouts cannot silently lose or shift rows through merged or multi-row
headers, formula caches, duplicate target categories or four-digit index ambiguity. Return exact
source/test references, focused results and minimal synthetic reproductions for every gap.
