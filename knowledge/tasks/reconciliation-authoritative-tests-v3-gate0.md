---
type: orchestration
status: frozen
orda_status: frozen_in_admin_integration_merge
work_id: reconciliation-authoritative-tests-v3
objective: Prove authoritative global decisions change matching, calculation, feedback suppression, API state, and final XLSX without legacy passive cards.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
integration_parent_sha: 24eb0be4e698c85a0b681d7b0cf15e525e2a8333
admin_feature_sha: 736beb8266765e2e8026aa0c248e25c798125216
published_base_sha_source: admin merge commit containing this manifest and frozen card
wave: 1
max_parallel: 1
max_spawns: 2
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-02T04:28:00+08:00
tags:
  - knowledge/orchestration
  - status/frozen
  - domain/document-processing
  - layer/test
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-tests-v3]]"
---

# Gate 0: authoritative focused tests

Production is frozen. This wave edits only focused tests. It replaces the two
obsolete passive-card assertions and adds direct evidence for global grouping,
multi-selection, row priority, feedback, stale versions, rollback and XLSX cells.

Baseline at admin feature handoff: 21 admin units pass; full existing admin set
has 29 passing tests and exactly two obsolete legacy passive-card failures;
Ruff, format, Node and diff-check pass.
