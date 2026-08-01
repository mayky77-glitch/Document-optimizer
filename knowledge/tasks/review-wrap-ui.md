---
type: task
status: done
work_id: drawing-card-million-values-v3
role: worker
agent_role: designer
owner: "review-wrap-designer"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Responsive overflow correction in decision controls"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-01
updated: 2026-08-01
write_scope:
  - "src/report_processor/admin_panel/assets/drawing-card.css"
source_paths:
  - "src/report_processor/admin_panel/assets/drawing-card.css"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
  - "drawing-card"
  - "ui"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Перенос длинных controls на второй ряд

## Goal

Prevent segmented labels from escaping their control and move decision controls or actions to a second row when horizontal space is insufficient, in both themes.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `src/report_processor/admin_panel/assets/drawing-card.css`
  - `knowledge/tasks/review-wrap-ui.md`
- Commands and tests run:
  - `curl -I --max-time 5 http://127.0.0.1:8765/drawing-card` — HTTP 200.
  - Playwright via installed Google Chrome: injected a read-only temporary review-card fixture and checked 1885, 900, 650, 390 and 320 px in light and dark themes. Every panel, segmented option and action button had `scrollWidth <= clientWidth`; at 900 px actions moved to the second grid row; at 650 px controls became separate rows.
  - Keyboard focus check: focused `Количество + стоимость` exposes `rgb(255, 201, 40) solid 3px` outline with 3px offset.
  - `uv run pytest -q tests/integration/test_drawing_card_ui_contract.py` — 3 passed, 1 expected stale-contract failure. `test_review_decision_layout_uses_bounded_desktop_columns_and_compact_actions` asserts the previous fixed 320px mode column and must be updated by `million-feedback-tests` for the new responsive contract.
- Result:
  - Decision panel uses its review-card width as responsive container. Long mode label wraps inside its segment; it cannot render beyond its border.
  - At constrained card widths, action buttons move to the second row. At narrower widths, category, mode and actions form readable rows without horizontal scroll.
  - Both light and dark theme tokens remain in use; no HTML or JavaScript changed.
- Risks or follow-up:
  - `@container` is required for width-aware row switching; supported by current Chromium/Firefox/Safari. Test contract must be changed with the behavior, not preserved as a literal old CSS string.

## Handoff

Ready for orchestration review.
