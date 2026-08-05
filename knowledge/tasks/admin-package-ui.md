---
type: task
status: ready
tags: [status/ready, capability/reconciliation, surface/admin, domain/design]
assigned_profile: L1
assigned_grade: P3
---

# Admin package reconciliation UI and guide

Base: `953eec7e4bf571ca076d48d3c486bf66bd716584`.

Own: `src/report_processor/admin_panel/assets/**`, UI-contract tests and README
usage text. Do not edit Python application/service files or backend tests.

Add `/package-reconciliation` and `/help` pages in the existing visual language,
wire folder selection through `webkitRelativePath`, show progress, status counts,
evidence rows and JSON download, and add consistent navigation to all pages. Copy
must explain when to use each workflow, what inputs are accepted, what every status
means, that PDFs are optional evidence, local-processing/privacy behavior and common
recovery actions. Preserve dark
mode, focus states, reduced motion and small-screen usability.
