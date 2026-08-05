---
type: task
status: done
tags: [status/done, capability/reconciliation, surface/admin]
assigned_profile: L1
assigned_grade: P3
---

# Admin package reconciliation backend

Base: `953eec7e4bf571ca076d48d3c486bf66bd716584`.

Own: `src/report_processor/admin_panel/app.py`, `view.py`, new package admin service,
backend-focused unit/integration tests. Do not edit HTML, CSS, JavaScript, README or
other workers' files.

Deliver a safe folder-upload API, private job/result storage, injected test seam,
controlled public errors, JSON download and routes for the new workflow and guide.
Validate relative paths, type/count/combined size and duplicate names. Require at
least one workbook; PDFs are optional evidence and Excel-only folders must run. Run the
accepted synchronous reconciliation in a thread pool. Never return raw OCR or
absolute paths.

## Completion evidence

- Safe folder upload, private job storage and bounded JSON result are integrated.
- Excel/LibreOffice-only packages run normally; PDF evidence remains optional.
- LibreOffice Calc `.ods` is converted only in a private isolated safe-mode
  profile; the original file and public relative path remain unchanged.
- Accepted in checkpoint `41943ec9141f6b6cdf5ddbd978c239c35423f313`.
