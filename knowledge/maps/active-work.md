---
type: map
tags:
  - knowledge/map
  - status/in-progress
last_verified: 2026-08-13
updated: 2026-08-13
---

# Active work

Active verification implementation:
[[../tasks/admin-verification-accuracy-remediation|Accuracy remediation]] with
[[../tasks/admin-verification-remediation-gate0|frozen ORDO Gate 0]]. Owner decisions for numeric
J/K verification and target-stage selection are accepted. Completed discovery audit:
[[../tasks/reconciliation-max-accuracy-audit-v1|Максимальная точность проверки и сверки]]; findings
remain tracked in [[../errors/reconciliation-accuracy-findings|RA-001—RA-018]] until verified closed.
Numeric/stage remediation is integrated; the sequential lifecycle wave is accepted at `c8da710`.
The active dependency chain is [[../tasks/reconciliation-real-layout-gate0|Real-layout Gate 0]]:
structural source/identity → structural target oracle → reporting-period insertion and release
shadow.

Active Qdrant plan: [[../tasks/qdrant-dense-rag-implementation-plan|Dense RAG implementation]].

Wave 1: [[../tasks/qdrant-dense-rag-core|core]] and
[[../tasks/qdrant-dense-rag-infra|local service/infra]]. Wave 2:
[[../tasks/qdrant-dense-rag-indexer|indexer/evaluation]] and
[[../tasks/qdrant-dense-rag-app|application integration]].

Link only active task cards here. Remove or move links after orchestration accepts completion.

No active drawing-card initiative. Completed/recent:
[[../tasks/drawing-card-contract-check-rag-plan|Договорные значения и RAG feedback]].

Completed admin integration: [[../tasks/admin-package-backend|safe Excel/PDF API]],
[[../tasks/admin-package-ui|workflow UI/guide]],
[[../tasks/admin-verification-ooxml|red-row OOXML]],
[[../tasks/admin-verification-service|verification service/API]] and
[[../tasks/admin-verification-ui|verification/report UI]].

Completed global package review:
[[../tasks/reconciliation-global-batch-review-v5-final|Reconciliation global batch review v5 final]].

Completed reconciliation handoff: [[../tasks/reconciliation-real-data-resilience-v4-final]].

Completed Excel-PDF Wave 10: [[../tasks/excel-pdf-wave10-final]].

- [[../ORCHESTRATION|Orchestration rules]]
- Последняя принятая волна: [[../tasks/summary-layout-xlsx|Карточная XLSX-сводка]],
  [[../tasks/summary-layout-ui|компактная панель решений]] и
  [[../tasks/summary-layout-tests|регрессии layout]].
