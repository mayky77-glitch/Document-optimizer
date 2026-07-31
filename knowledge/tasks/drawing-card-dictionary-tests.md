---
type: task
status: claimed
work_id: drawing-card-dictionary-v1
role: worker
agent_role: tester
owner: "dictionary-tester-1"
profile: L1
routing_grade: P3
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Deterministic positive, negative, cost-only, unit and no-impact matrix"
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
write_scope:
  - "tests/unit/drawing_card/test_dictionary_masks.py"
  - "tests/unit/drawing_card/test_matcher_dictionary.py"
  - "tests/unit/drawing_card/test_inline_review_flow.py"
  - "tests/unit/admin_panel/test_drawing_card_service.py"
  - "tests/integration/test_drawing_card_admin.py"
source_paths:
  - "src/report_processor/drawing_card/matching/**"
  - "src/report_processor/drawing_card/resources/rules.json"
depends_on:
  - "dea20106129bd3b89446990427cc706b63e81f4a"
tags:
  - "task/tests"
  - "status/claimed"
  - "drawing-card"
  - "matching"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Verify confirmed dictionary and masks

## Frozen acceptance

- Cover every supplied phrase applicable to the existing eight categories.
- Cover cable default/low-current precedence, exclusions and positive exceptions.
- Cover `м/к`, known typo, cost-only and metal exclusions.
- Cover concrete/pile/TT/ZRA positives, units and exclusions.
- Cover exact feedback precedence over generic masks.
- Cover blank/zero no-impact rows and impactful one-sided zero rows.
- Cover typo tolerance boundaries, ambiguity and manual-review fallback.
- Regress category target-unit update and cost-only persistence.
- Assert RuBERT Tiny2 remains suggestion-only.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave in review until integration accepts the test commit.
