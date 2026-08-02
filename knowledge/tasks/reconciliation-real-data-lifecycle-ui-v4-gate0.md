---
type: orchestration
status: frozen
work_id: reconciliation-real-data-lifecycle-ui-v4
objective: Correct target semantics and integrate fail-soft source issues into the authoritative grouped review UI.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: 3145c8cb74e673bb67f097e773f869573c90afc1
published_base_sha_source: root Wave 2 planning commit containing this manifest and frozen card
wave: 1
max_parallel: 1
max_spawns: 2
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-02T13:25:00+08:00
tags:
  - knowledge/orchestration
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-lifecycle-ui-v4]]"
---

# Gate 0: reconciliation lifecycle and UI

## Accepted dependency

- Source/core feature: `c46fe72bed4b5ff347e30b451abb2cdd6cd4d9e0`.
- Accepted merge: `3145c8cb74e673bb67f097e773f869573c90afc1`.
- Root validation: 2,940 real cumulative rows, 498 deterministic groups, one
  controlled source issue and zero hierarchy-like units.

## New diagnosis

The generic target semantic recovery binds this documented table with a four-column
shift. Real target rows therefore have no usable `object_code`, `work_name`, stage or
document index; all 173 matches are unmatched and every proposed category is empty.
Wave 2 must fix the integration adapter rather than weaken the matching engine.

## Acceptance

- Real target layout yields the selected stage, non-empty object/category/unit fields,
  a small deduplicated global Russian category catalog and non-zero proposals.
- Applying a global group maps each member by its source main index to one concrete
  target row, respects a row exception, preserves unmatched target rows, writes only
  J/K through the existing verified writer, and keeps all source/target inputs immutable.
- Partial/all-source failures and public basename guidance follow the frozen card.
- Focused tests are intentionally deferred to the independent tester wave.

