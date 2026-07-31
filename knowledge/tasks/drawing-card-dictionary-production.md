---
type: task
status: claimed
work_id: drawing-card-dictionary-v1
role: worker
agent_role: developer
owner: "dictionary-developer-1"
profile: L2
routing_grade: P4
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Consequential multi-rule classification, unit guards and feedback precedence"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-31
updated: 2026-07-31
write_scope:
  - "src/report_processor/drawing_card/matching/matcher.py"
  - "src/report_processor/drawing_card/matching/masks.py"
  - "src/report_processor/drawing_card/resources/rules.json"
source_paths:
  - "src/report_processor/drawing_card/matching/**"
  - "src/report_processor/drawing_card/resources/rules.json"
depends_on:
  - "dea20106129bd3b89446990427cc706b63e81f4a"
tags:
  - "task/implementation"
  - "status/claimed"
  - "drawing-card"
  - "matching"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Confirmed dictionary and masks

## Frozen contract

- Order: current-run approval, no-impact check, exact confirmed feedback, strict
  exclusions/unit guards, deterministic dictionary/masks, lexical/RuBERT/manual.
- Blank name or quantity and cost both absent/zero is explicit no-impact exclusion.
  Unknown formula values are not hidden.
- Exact user feedback must not be shadowed by a broad deterministic mask.
- Whitespace, NBSP, case and `ё` normalize. Minor typo tolerance applies only to
  distinctive long tokens; weak/tied matches require review.
- Generic cable text defaults to power cable unless explicit low-current marker:
  `слаботоч`, `ВОЛС`, networks/communication, `КИП`, automation.
- Exclude cable-core connection and device wiring. Preserve confirmed positive
  mappings for cable boxes/trays and the supplied grounding phrase.
- `м/к` means metal structures. `Стоимость м/к` is cost-only. Exclude lightning
  and antenna masts and tank fabrication.
- Add supplied concrete, pile, TT and ZRA phrases. Piles exclude all testing.
  Concrete quantity auto-applies only to cubic-metre units; incompatible
  reinforced-concrete rows never auto-apply.
- Only the existing eight categories may enter output. Do not invent categories
  for welding, backfill, trench, VL or VOLS without a target schema.
- RuBERT Tiny2 remains the smallest offline semantic model and suggestion-only.
- Do not change admin/service code: category target-unit updates and cost-only
  aggregation are already implemented.

## Completion evidence

- Changed paths:
- Commands and tests run:
- Result:
- Risks or follow-up:

## Handoff

Leave in review until integration accepts the feature commit.
