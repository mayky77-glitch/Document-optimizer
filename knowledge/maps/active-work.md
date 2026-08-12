---
type: map
tags:
  - knowledge/map
  - status/in-progress
last_verified: 2026-08-12
updated: 2026-08-12
---

# Active work

Active reconciliation audit:
[[../tasks/reconciliation-max-accuracy-audit-v1|Максимальная точность сверки документов]].
Scope: current production path, original/result workbook reconciliation, adversarial
edge cases and knowledge refresh. ORDA allows eight total subagent launches in waves,
with no more than three concurrent.

Current result: real wrong-output finding RA-001 plus deterministic high/medium gaps are
catalogued in [[../errors/reconciliation-accuracy-findings|reconciliation accuracy findings]].
Only final test/knowledge/P6 synthesis remains; remediation is deliberately separate.

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
