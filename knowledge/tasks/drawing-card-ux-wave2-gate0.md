---
type: orchestration
status: frozen
work_id: drawing-card-ux-wave2-v1
objective: Move drawing-card processing out of the upload request and make job state recoverable, cancellable and idempotent without weakening private-path or artifact safety.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ux-wave2
planning_parent_sha: 9b71ebcb85659b99ca4bae3c326f62c0be6353aa
published_base_sha_source: planning commit containing this manifest and both frozen task cards
wave: 2
max_parallel: 2
max_spawns: 4
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-06T14:35:00+08:00
---

# Gate 0: drawing-card UX Wave 2

## Precedence and compatibility

Current source, Wave 1 contracts, passing tests and confirmed corrections from the user session
override stale examples in the UX specification. This wave changes lifecycle mechanics only:

- extraction, comparable-period, hierarchy, matching, review-packet and feedback decisions remain
  semantically unchanged;
- the existing public job payload is extended additively; stable fields and path redaction remain;
- uploaded workbooks stay private, immutable and untracked; manifests contain only validated
  job-relative paths and controlled metadata;
- a retry uses a distinct attempt directory and never reuses a partial output;
- cancellation is cooperative and fail closed: no result URL is published until validation ends;
- restart recovery reopens valid manifests and resumes queued/processing attempts from retained
  private uploads without asking the user to upload again;
- accepted review decisions are persisted atomically as job state, while durable domain feedback
  is still appended only after a successfully validated final result.

No user workbook, generated workbook, absolute source path, workbook content or untracked master
specification is added to Git.

## Dependency graph

1. Parallel task `workflow-lifecycle` owns phase/progress/cancellation hooks in the deterministic
   workflow. It does not implement threads, HTTP or disk manifests.
2. Parallel task `private-job-store` owns a bounded atomic JSON manifest store with hostile-path
   rejection. It does not import the admin service or workflow.
3. Integration owner merges both with `--no-ff`, then owns service locking/background execution,
   recovery, idempotency, retry/cancel routes and UI polling.
4. A P6 read-only review closes the wave after focused, restart, cancellation and full validation.

## Shared contracts

- `DrawingCardLifecycle-1.0`: phases are `upload`, `schema_detection`, `extraction`,
  `hierarchy_filtering`, `matching`, `review_preparation`, `output_writing`, `validation`, `ready`.
- `DrawingCardProgress-1.0`: phase, processed/total files, processed/total rows when known, UTC
  started/updated timestamps and a controlled terminal cause.
- `DrawingCardPrivateManifest-1.0`: schema-versioned bounded JSON, only safe relative paths,
  atomic temp+fsync+replace, mode `0600`, corrupt/hostile records ignored.
- `DrawingCardAttempt-1.0`: monotonic attempt number and isolated `attempts/NNNN` artifacts.
- `DrawingCardIdempotency-1.0`: one user upload key maps to one job; duplicate POST does not create
  or schedule another job.

## Baseline

- Focused Wave 2 baseline: 50 tests passed.
- Scoped Ruff baseline: passed.
- Wave 1 full baseline: 1492 passed, 25 skipped.

## Release acceptance

- `POST /api/drawing-card/jobs` returns a persisted job status without waiting for workflow work.
- The UI polls at most every five seconds and restores its active job after reload.
- Every state-changing review action persists before the response is published.
- A fresh service instance recovers valid jobs and decisions; corrupt manifests and unsafe paths
  are skipped without leaking or reading outside their job directory.
- Cancellation removes partial attempt output and never publishes an XLSX.
- Retry increments the attempt and cannot mix old and new artifacts.
- Existing synchronous test doubles remain usable through an explicit executor/test seam rather
  than preserving synchronous production HTTP behavior.
