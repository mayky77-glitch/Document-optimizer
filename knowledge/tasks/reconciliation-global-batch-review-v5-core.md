---
type: task
status: draft
orda_status: frozen
card_id: reconciliation-global-batch-review-v5-core
version: 1
work_id: reconciliation-global-batch-review-v5
task_id: core
purpose: Build deterministic safe packages, zero-activity filtering and optional local semantic assistance.
role: worker
agent_role: developer
owner: reconciliation-v5-core
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: Difficult multi-file domain implementation with hard safety constraints and optional local-model fallback.
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
card_path: knowledge/tasks/reconciliation-global-batch-review-v5-core.md
card_commit_sha_ref: launch_envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/reconciliation-v5-core
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - src/report_processor/reconciliation_grouping
  - tests/unit/reconciliation_grouping
  - tests/contract/test_reconciliation_grouping_contract.py
source_paths:
  - src/report_processor/reconciliation_grouping
  - tests/unit/reconciliation_grouping
  - tests/contract/test_reconciliation_grouping_contract.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/reconciliation_review
  - src/report_processor/stage_rag
  - tests/integration
  - pyproject.toml
  - uv.lock
contract_versions:
  input: ReconciliationFeatureContract-1.0
  output: ReconciliationPackageContract-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/reconciliation_grouping tests/contract/test_reconciliation_grouping_contract.py tests/integration/test_block18_rag.py
  - uv run ruff check src/report_processor/reconciliation_grouping tests/unit/reconciliation_grouping tests/contract/test_reconciliation_grouping_contract.py
  - uv run ruff format --check src/report_processor/reconciliation_grouping tests/unit/reconciliation_grouping tests/contract/test_reconciliation_grouping_contract.py
  - git diff --check
last_verified: 2026-08-02
updated: 2026-08-02
tags:
  - task/implementation
  - status/draft
  - domain/document-processing
  - risk/high
links:
  - "[[reconciliation-global-batch-review-v5-plan]]"
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Reconciliation global batch review v5 core

## Frozen contract

- Recompute `zero_activity` on every upload. Only finite Decimal quantity and cost
  both equal to zero are hidden. Keep rows in source data; exclude them from review,
  unresolved, packages and feedback.
- Every visible row belongs to exactly one existing group, semantic family and
  package. Preserve exact group membership and stable ordering.
- Package boundary is category, accounting mode, compatible unit family, action
  and object. Hard constraints run before semantic similarity. Conflicts become
  explicit exceptions.
- Local RuBERT is optional, pinned, local-only and fail-soft. Its output may rank or
  flag exceptions, never decide, calculate or write XLSX.
- Package versions bind exact membership and version inputs. Public consumers see
  only opaque IDs and versions.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave this card in `review` until ORDA integration accepts the feature and merge SHAs.
