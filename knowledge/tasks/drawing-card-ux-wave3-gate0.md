---
type: task
status: frozen
card_id: drawing-card-ux-wave3-gate0
version: 1
wave: 3
base_sha: 432753ce1f65b8b75e90040899de2227f276b9ae
branch: codex/drawing-card-ux-wave3
---

# Wave 3 Gate 0

Wave 3 accelerates review without weakening fail-closed matching. It combines the UX specification
with the accepted feedback/packet requirements from the current task.

Frozen decisions:

- no Qdrant, RAG expansion, DBSCAN or automatic financial confirmation;
- legacy `ReviewFeedbackStore-1.0` is not eligible for automatic replay;
- new feedback is an append-only, private, atomic `DrawingCardFeedback-2.0` ledger;
- the local default tenant is explicit, while project scope is derived from immutable input hashes;
  exact input hashes remain part of every replay key, so the default is deliberately conservative;
- normal matching runs first; only a manual-review candidate may be removed from the queue by one
  fully exact, active, hazard-free feedback entry;
- packet membership is exact, versioned and membership-complete; hazards are always singleton;
- current cluster endpoints remain additive-compatible, but their server implementation uses the
  stricter packet context;
- categories, labels and units come from the server payload/API; browser category constants are
  removed;
- feedback is committed atomically for all row decisions and applicable packet decisions before
  a confirmed page rerun starts; persistence failure leaves the page retryable;
- input sources remain immutable and no user workbook is added to Git.

Integration owner scope:

- add tenant/project/rules/model/input context to workflow and private job state;
- apply exact feedback after deterministic matching and before queue formation;
- atomically persist page feedback and packet audit before rerun;
- expose controlled source context, filters, categories, packet flags and review metrics;
- add lifecycle, tenant isolation, invalidation, hazard, atomicity and audit integration tests.
