---
type: task
status: frozen
card_id: drawing-card-ux-wave3-review-ui
version: 1
supersedes: null
work_id: drawing-card-ux-wave3-v1
task_id: review-ui
purpose: Implement accessible filtered packet review UX against the additive Wave 3 server payload.
role: designer
card_path: knowledge/tasks/drawing-card-ux-wave3-review-ui.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 432753ce1f65b8b75e90040899de2227f276b9ae
branch: codex/drawing-card-ux-wave3-review-ui
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/assets/drawing-card-review.js
  - src/report_processor/admin_panel/assets/drawing-card.html
  - src/report_processor/admin_panel/assets/drawing-card.css
  - tests/integration/test_drawing_card_ui_contract.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_review_payload.py
  - src/report_processor/drawing_card
  - knowledge
  - docs
contract_versions:
  input: DrawingCardReviewPacketPayload-2.0
  output: DrawingCardReviewUX-2.0
acceptance_commands:
  - uv run pytest -q tests/integration/test_drawing_card_ui_contract.py
  - node --check src/report_processor/admin_panel/assets/drawing-card-review.js
  - git diff --check
---

# Packet review UX

Remove the browser `CATEGORIES` constant. Consume `review_categories` entries (`id`, `label`,
`units`) from the review API. Add filters for reason, category, safe filename and confidence, with
`only_unresolved=true` by default. Send filters as query parameters and keep filter state, current
page/card and expanded member details in `sessionStorage` per job.

Display packet/singleton/hazard labels, member source basename/sheet/row, position, drawing code,
name, unit, Russian-formatted quantity/cost, confidence explanation and server-provided Russian
reason. Keep wide member tables inside their own horizontal scroll container. After save, focus the
next unresolved packet. Add a per-member exclude/override affordance using the existing row review
endpoint, with visible warning that it removes the row from packet fanout.

Add a sticky mobile bar at 390 px with remaining count and Next action. All primary actions must be
keyboard reachable with visible focus. Never add an unconditional approve-all action.
