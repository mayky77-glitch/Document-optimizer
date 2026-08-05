---
type: task
status: ready
tags: [status/ready, capability/reconciliation, surface/admin, domain/design]
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
