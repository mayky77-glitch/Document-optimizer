---
type: task
status: frozen
card_id: reconciliation-mobile-overflow-v4
version: 1
purpose: Remove the measured 10 px mobile overflow from hidden review table headings.
role: designer
owner: reconciliation-mobile-overflow-designer
profile: L1
routing_grade: P3
routing_reason: Single responsive CSS defect with an exact browser measurement.
planning_parent_sha: 1f4083e7ec2967409fdb14ff49701c4eb3077cfb
branch: codex/reconciliation-mobile-overflow-v4
write_scope:
  - src/report_processor/admin_panel/assets/admin.css
forbidden_paths:
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/app.py
  - tests
acceptance_commands:
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - capability/admin-panel
  - layer/frontend
  - risk/low
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Mobile overflow remediation

At 390 px the document measures `scrollWidth=400`, with the hidden table `thead`
and its child `th` cells contributing the extra width. Mobile cells already expose
their labels through `data-label`; remove the hidden heading row from mobile layout
without changing desktop tables, card controls, themes or JavaScript.
