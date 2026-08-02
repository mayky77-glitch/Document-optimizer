---
type: orda_task
status: frozen
card_id: reconciliation-real-data-lifecycle-ui-v4
version: 2
supersedes: null
work_id: reconciliation-real-data-lifecycle-ui-v4
task_id: reconciliation-real-data-lifecycle-ui-v4
purpose: Correct the target layout, preserve safe upload names, integrate source issues, and present clear authoritative grouped cards.
role: developer
owner: reconciliation-real-data-lifecycle-ui-developer
card_path: knowledge/tasks/reconciliation-real-data-lifecycle-ui-v4.md
card_commit_sha_source: exact Wave 2 planning commit supplied by Gate 0 launch envelope
profile: L1
routing_grade: P3
routing_reason: Scoped lifecycle and responsive frontend integration after the source contract is accepted.
reasoning_effort: medium
assigned_model: gpt-5.6-terra
launch_status: planned
planning_parent_sha: 3145c8cb74e673bb67f097e773f869573c90afc1
base_sha_source: exact Wave 2 planning commit supplied by Gate 0 launch envelope
dependency_shas:
  - 3145c8cb74e673bb67f097e773f869573c90afc1
branch: codex/reconciliation-real-data-lifecycle-ui-v4
write_scope:
  - src/report_processor/admin_panel/reconciliation_uploads.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/reconciliation_review_presentation.py
  - src/report_processor/admin_panel/assets/index.html
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/assets/admin.css
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/reconciliation_review
  - src/report_processor/processing
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - tests
contract_versions:
  input: ReconciliationSourceBatch-1.0
  output: ReconciliationReviewPresentation-2.0
acceptance_commands:
  - .venv/bin/ruff check src/report_processor/admin_panel/reconciliation_uploads.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/service.py src/report_processor/admin_panel/presentation.py src/report_processor/admin_panel/reconciliation_review_presentation.py
  - .venv/bin/ruff format --check src/report_processor/admin_panel/reconciliation_uploads.py src/report_processor/admin_panel/reconciliation_target.py src/report_processor/admin_panel/reconciliation_execution.py src/report_processor/admin_panel/service.py src/report_processor/admin_panel/presentation.py src/report_processor/admin_panel/reconciliation_review_presentation.py
  - node --check src/report_processor/admin_panel/assets/admin.js
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - domain/document-processing
  - capability/admin-panel
  - layer/full-stack
  - risk/medium
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-resilience-v4-gate0|Gate 0]]"
---

# Reconciliation lifecycle and UI

## Frozen target and classification contract

- Add a focused target-layout adapter. For the documented reconciliation table,
  bind object scope/index/name/category/unit from A/B/C/E/F and writable selected
  quantity/cost from J/K. Do not change the generic target reader or writer.
- Carry object index/name through block rows and keep only the explicitly selected
  stage. Normalize the terminal object index from target column B and the main index
  from each safe source filename according to the attached specification.
- Public category IDs represent stable global work types, not physical workbook rows.
  Labels are short Russian target work names. Proposals collapse compatible rule
  candidates to that global type. At apply time, expand each group decision to rows
  and route every row to its concrete target row by source main index + category.
  Row overrides win. A category unavailable for any member must be rejected before
  final apply with a controlled Russian message.
- The authoritative write set contains only calculated target rows selected by the
  complete operator decisions. Unmatched target rows remain byte-for-byte unchanged;
  they must not create hidden manual-review blockers.
- Preserve the current `Decimal` calculation, coefficient `2.7`, existing writer
  package verification, and durable feedback. Do not build a second calculation path.

## Frozen upload and failure contract

- Move upload filename/content validation and safe-name normalization from
  `service.py` to `reconciliation_uploads.py`; `service.py` must have neutral or
  negative net line growth and remain below 700 lines. `app.py` is forbidden.
- Store the ordered original NFC basenames in `AdminJob.source_names`, aligned with
  private paths/digests. Public payloads expose a basename only inside a controlled
  source issue.
- A partial source failure keeps the job in review with good groups plus issue cards.
  An all-source failure keeps safe issue metadata and status `failed`; it never shows
  the empty/ready message and never leaks the exception. Target-layout failure is a
  separate safe target error.
- The UI truthfully accepts only extensions supported by this flow. Do not advertise
  `.xlsb` unless production readers and validation both support it.

## Frozen presentation and interaction contract

- Public payload includes only `review_groups`, global `review_categories`, unresolved
  card count, apply flag, and controlled `source_issues` with `basename`, `comment`,
  `repair_hint`, `can_continue`. Paths, sheets, coordinates, formulas, provenance,
  evidence, raw warnings and exception text are forbidden.
- Count unresolved cards, not rows. Every expandable group still contains every member
  row. All quantities/costs render with exactly two decimals.
- Keep one category select, the existing direct two-position mode switch, one group
  accept/reject action pair, and the same compact row override. No dropdown for the
  two-state mode and no duplicate confirmation buttons.
- Failed/all-bad jobs show file problem cards and a short retry instruction. The
  empty-review message is shown only for a genuinely ready job.
- Light/dark and 1440/390 px must have no horizontal page/card overflow. Do not start
  the service; root owns restart and browser smoke.

## Handoff evidence

Move to review only with changed paths, feature SHA, target-layout probe showing
non-empty global proposals, safe basename issue payload, `service.py` line delta,
Ruff/format/Node/diff results, risks and merge order. Do not edit tests or merge.

