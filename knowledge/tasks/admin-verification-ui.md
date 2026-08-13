---
type: task
status: done
tags: [status/done, capability/reconciliation, surface/admin, domain/design]
assigned_profile: L1
assigned_grade: P3
---

# Verification and report-composition UI

Base: `41943ec9141f6b6cdf5ddbd978c239c35423f313`.

Own only `src/report_processor/admin_panel/assets/**`, `README.md` and UI-contract
tests. `/` must submit `operation=verify`, explain its source+comparison inputs,
hide manual-review controls for verification, show the exact all-good message on
pass, and offer the annotated report on failure. Present `/drawing-card` in nav and
copy as «Составление отчёта» with built-in auto-reconciliation while retaining the
card workflow. Update help/navigation consistently. Preserve current design tokens,
dark mode, keyboard behavior, reduced motion and mobile layout.

## Completion evidence

- `/` is «Проверка документов» and submits explicit verification.
- `/drawing-card` is «Составление отчёта» and explains built-in auto-reconciliation.
- Clean and failed outcomes render without manual-review controls; the latter
  offers the red-row workbook/ZIP.
- Desktop/mobile browser smoke passed without console, page or external-request errors.

## Post-acceptance audit

The UI has no target-stage control and therefore relies on the server's silent `13.1` default.
The owner must approve explicit selection, safe discovery or a documented strict default before
accuracy remediation. See [[../errors/reconciliation-accuracy-findings|RA-017]].
