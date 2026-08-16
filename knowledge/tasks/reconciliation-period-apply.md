---
type: orchestration
status: accepted
work_id: reconciliation-period-apply-v2
objective: Preview and apply one reporting period with strict verification and restart-safe evidence.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: 90e7a73aa156897c60fc507a420ff805e0ba4474
published_base_sha_source: exact planning commit containing this manifest and both task cards
wave: 1
max_parallel: 1
max_spawns: 3
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-14T13:00:00+08:00
accepted_at: 2026-08-16
published_preview_sha: fe118b96999ad398506e7d9c8da50f8fd420bad3
published_apply_sha: dac566aee43a1a0fae81e04c34464cf1c9720280
tags:
  - task/implementation
  - status/accepted
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[reconciliation-period-preview|Target preview]]"
  - "[[reconciliation-period-apply-service|Apply and recovery]]"
  - "[[reconciliation-period-insertion-gate0|Parent Gate 0]]"
  - "[[../errors/reconciliation-accuracy-findings|RA-021]]"
---

# Period preview/apply Gate 0

Accepted. Preview is published at `fe118b9`; apply/recovery is published at `dac566a`. Later
semantic versioning supersedes the original identity/manifest versions below with
`ReconciliationTargetIdentity-2.0` and `AdminReconciliationJobManifest-4.0`.

Published dependency is `main@90e7a73`: direct OOXML insertion and bounded wholly-left shared
formulas are accepted. CodeGraph confirmed that the prior single-task card was unsafe because it
forbade `service.py`; reporting period and replay evidence cannot survive restart without the job
manifest. This corrected plan has two sequential tasks and no API/UI changes.

[[reconciliation-period-preview|Wave A]] owns structural target selection, historical-target
preview, virtual future cells and target identity. [[reconciliation-period-apply-service|Wave B]]
owns calculation/apply/recovery and begins only from accepted Wave A integration. `verify` stays on
the strict physical target reader and may never import or call the planner, preview or transformer.

## Shared contracts

- `ReconciliationTargetSelection-1.0`: target base fields bind through logical schema roles and
  hierarchical headers; ambiguity fails closed without fixed A–F columns or phrase ranking.
- `ReconciliationTargetInsertionPreview-1.0`: non-writable virtual quantity/cost cells use each
  plan anchor's future adjacent coordinates; all other row facts come from the immutable target.
- `ReconciliationTargetIdentity-2.0`: digest of original target SHA, selected stage, nullable
  canonical period and nullable plan digest. Catalog/package/state/target/apply identities consume it.
- `ReconciliationCalculationSemantics-1.0`: canonical sorted JSON of calculation ID, target row ID,
  status and writer-adapted quantity/cost exact Decimal strings/null.
- `ReconciliationApplyIntegrity-3.0`, `AdminReconciliationJobManifest-4.0` and
  `ReconciliationApplyReplay-2.0`: period, plan, target identity and calculation digests are durable
  replay evidence; manifests contain no workbook values, formulas, sheets or coordinates.

## Release sequence

Apply freezes decisions and immutable input snapshots, computes preview calculations, and treats
zero as actionable while null/null is not. No actionable value publishes the original target
byte-for-byte and never creates a prepared workbook. An actionable missing-pair path transforms one
private snapshot, strict-rereads it, rebuilds catalog/matches/calculations and requires identical
target IDs plus semantic calculation digest before the existing writer. Existing physical period
pair is idempotent; mixed or unsupported topology fails closed.

Recovery reconstructs period-aware review and calculation evidence without transformer/writer,
matches all manifest digests, then exact-replays the SQLite commit. Old v2/v3 manifests are
intentionally rejected. API/UI reporting-period input and the final private/full release shadow are
accepted at product checkpoint `4294c15`.
