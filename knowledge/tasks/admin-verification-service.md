---
type: task
status: done
tags: [status/done, capability/reconciliation, surface/admin]
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

## Completion evidence

- `operation=verify|reconcile` is additive; omitted operation remains reconcile.
- Clean verification returns the exact success message without an artifact.
- Failed verification returns one annotated workbook or a ZIP containing every
  submitted source workbook once; technical failures never appear as a clean result.
- Safe basenames are limited to repair guidance; paths, sheets, coordinates,
  values and formulas remain private.

## Post-acceptance audit

The 2026-08-13 real-workbook audit supersedes the former accuracy/release implication while
preserving this historical implementation record. Verification currently proves package/feedback
classification, not numeric equality; an empty target-stage catalog is accepted and turns all
visible rows into failures. See [[../components/document-verification|current component contract]]
and [[../errors/reconciliation-accuracy-findings|RA-014/RA-017]].
