---
type: task
status: ready
tags: [status/ready, capability/reconciliation, surface/admin]
assigned_profile: L2
assigned_grade: P4
---

# Verification service and API

Base: `41943ec9141f6b6cdf5ddbd978c239c35423f313`.

Own only new `admin_panel/reconciliation_verification.py`, `admin_panel/service.py`,
`admin_panel/presentation.py`, `admin_panel/app.py`, and focused service/API tests.
Add explicit `operation=verify|reconcile`, default reconcile. Use existing matching,
safe packages and authoritative feedback; RAG is non-authoritative. Call the agreed
OOXML annotator interface. Return exact clean/failed verification payloads without
location metadata. One source downloads an annotated workbook; multiple source
copies are a bounded safe ZIP. Preserve legacy reconciliation flow and controlled
failure for unreadable/partial inputs.
