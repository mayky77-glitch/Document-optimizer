---
type: orchestration
status: frozen
work_id: reconciliation-target-measure-v1
objective: Bind verification and reconciliation to one structurally proven current-period target quantity/cost pair.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: fe3d5eee01077c6130dd67b5f300d20fb316f276
published_base_sha_source: exact planning commit containing this manifest and task card
wave: 1
max_parallel: 1
max_spawns: 3
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-13T15:30:00+08:00
tags:
  - task/implementation
  - status/in-progress
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[reconciliation-real-layout-gate0|Real-layout dependency plan]]"
  - "[[reconciliation-real-layout-target-measure|Target-measure task]]"
  - "[[../errors/reconciliation-accuracy-findings|RA-021]]"
---

# Reconciliation target-measure Gate 0

Published predecessor is source/identity checkpoint `fe3d5ee`; code and tests override this card.
The de-identified target/reference comparison proves that the historical documentary pair remains
unchanged while one adjacent current-period pair appears later. Its physical address is not part of
the contract. The reference pair has no common merged parent: both leaf paths carry one common
calendar-period identity. A valid detector therefore accepts either one coherent merged parent or
one common exact period identity across adjacent quantity/total-cost leaves.

Only [[reconciliation-real-layout-target-measure|target-measure]] writes in this work ID. One P4
developer works in an isolated branch; the integration owner merges `--no-ff`, runs the focused
gate and requests one independent P6 review. Private workbooks remain read-only and outside Git,
payloads, tests and orchestration state.

Period-column insertion, API/UI period input, source extraction, arithmetic, unit conversion and
writer production are forbidden in this wave. A target without a proven pair fails technically and
creates no red artifact. A later insertion wave may prepare the missing pair only after this reader
contract is accepted.
