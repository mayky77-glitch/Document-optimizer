---
type: map
tags:
  - knowledge/map
  - status/review
last_verified: 2026-08-16
updated: 2026-08-16
---

# Active work

The reconciliation accuracy release is published and CI-verified:

- [[../tasks/reconciliation-real-release-audit|Final release audit]] — accepted at product
  checkpoint `4294c15`; publication `2151751` and CI run `31949344330` passed.
- [[../tasks/reconciliation-source-region-implementation|Region-local source parser]] — accepted
  after private shadow and independent review.
- [[../tasks/reconciliation-zip-local-flags|ZIP local-header metadata]] — accepted after focused
  metadata and LZMA regressions.

No product implementation or release wave remains active for reporting-period reconciliation. The following
are completed dependencies retained for traceability:

- [[../tasks/reconciliation-period-ui|Reporting-period API/UI]].
- [[../tasks/reconciliation-writer-namespace-v3|Namespace-aware writer v3]].
- [[../tasks/reconciliation-period-insertion-gate0|Direct OOXML period insertion]].
- [[../tasks/admin-verification-accuracy-remediation|Numeric verification remediation]].
- [[../tasks/reconciliation-real-layout-gate0|Real-layout dependency history]].

Active Qdrant work is separate:
[[../tasks/qdrant-dense-rag-implementation-plan|Dense RAG implementation plan]].

Link only genuinely active task cards here. Move accepted implementation detail to the component,
decision, or completed task card.
