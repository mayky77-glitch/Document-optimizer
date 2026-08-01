---
type: orchestration
status: frozen
orda_status: frozen_in_core_integration_merge
work_id: reconciliation-authoritative-admin-v3
objective: Connect authoritative global reconciliation core to persisted admin decisions, safe APIs, rerun, and final XLSX delivery.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
integration_parent_sha: f75c668ec5c98bb48f071f2568779289fb048c57
core_feature_sha: 9a69de210563a58634994c731ce3e5e383af7e1a
published_base_sha_source: core merge commit containing this manifest and frozen card
wave: 1
max_parallel: 1
max_spawns: 2
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-02T04:10:00+08:00
tags:
  - knowledge/orchestration
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-authoritative-admin-v3]]"
---

# Gate 0: authoritative admin integration

## Frozen contract

- Replace the reconciliation page's journal-only lifecycle with job-local
  replaceable group/row decisions and an authoritative apply action.
- Apply always re-verifies private original uploads, invokes the accepted global
  core once, validates output, persists feedback, then exposes final XLSX.
- Feedback is target-scoped SQLite state, private mode `0600`, latest-wins. No
  path, sheet, coordinate, provenance, warning text or technical metric is public.
- Categories are opaque IDs bound to target digest and controlled target row;
  presentation exposes only ID and Russian label.
- `app.py` delegates route handlers and remains below 700 lines. New executable
  modules remain below 500 lines and each owns one responsibility.

## Baseline inherited from accepted waves

- Admin focused baseline: `31 passed`; targeted Ruff and Node passed.
- Core baseline after feature: `10 passed`; Ruff, compileall and diff-check passed.
- UI feature Node and diff-check passed.

## Successor test wave

During the admin feature merge, integration owner freezes the authoritative
test card into that exact merge commit. Tester then owns only tests and visual
smoke support; production code stays locked.
