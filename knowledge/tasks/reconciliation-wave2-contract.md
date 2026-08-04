---
type: task
status: done
work_id: reconciliation-wave2-v1
role: worker
agent_role: architect
owner: "wave2-contract"
profile: L3
routing_grade: P6
progress_revision: 0
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L3 compatibility profile maps to P6."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-sol
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope: []
source_paths: []
depends_on: []
tags:
  - "task/implementation"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 2 typed slots and skeleton contract

## Goal

Define the minimal immutable `TypedSlots-1.0` and semantic-skeleton contracts,
parsing precedence, slot impacts, ambiguity/conflict behavior and public API for
an isolated Wave 2 implementation over accepted Wave 1 canonical terms.

## Scope and instructions

- Modify only `write_scope` paths.
- Read-only: do not edit files or use Git.
- Cover DN/Du/D/d/diameter, PN/Ru/pressure, voltage ranges, cable core/section,
  length/mass/count, brand/material/execution, GOST/TU, fire class,
  model/article and document index as non-semantic identity.
- Preserve audit text and extracted spans separately; define deterministic
  overlap precedence and placeholder ordering.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: none; read-only architecture.
- Commands and tests run: plan/Wave 1/legacy contract inspection.
- Result: frozen TypedSlots-1.0 and SemanticSkeleton-1.0 API, precedence,
  impacts, warnings/conflicts and acceptance matrix.
- Risks or follow-up: explicit-only text properties and fail-closed ambiguous
  D/d and bare NxY forms.

## Frozen public contract

Modules only: `typed_slots.py` and `semantic_skeleton.py`. No legacy integration
or package-root re-export.

```python
TYPED_SLOTS_VERSION = "TypedSlots-1.0"
SEMANTIC_SKELETON_VERSION = "SemanticSkeleton-1.0"

parse_typed_slots(value: object, *, object_kind: str | None = None) -> TypedSlotParse
build_semantic_skeleton(
    value: object,
    *,
    category: str | None = None,
    object_kind: str | None = None,
    ontology: DomainOntology = DEFAULT_ONTOLOGY,
) -> SemanticSkeleton
```

Public models are frozen/slotted dataclasses; collections are tuple/frozenset;
numeric values are Decimal only. `TextSpan` uses Unicode code-point `[start,end)`
indexes into `normalize_audit_text(value)` and must reproduce `audit_fragment`.

Slot kinds: `diameter`, `pressure`, `voltage`, `cable_section`, `length`,
`mass`, `count`, `brand`, `material`, `execution`, `gost`, `tu`, `fire_class`,
`model`, `article`, `document_index`. Impacts: `category_neutral`,
`family_boundary`, `hard_conflict`, `display_only`.

- Diameter/pressure/voltage/cable section and brand/execution/standards/model/
  article are family boundaries.
- Material and fire class are hard conflicts.
- Length/mass/count are category-neutral.
- Document index is display-only/nonsemantic.
- DN/Du/DN, D/d/diameter/diameter-sign, PN/Ru, kV scalar/range,
  cores-x-section, explicit quantities and explicit text markers are supported.
- Bare D/d and NxY fail closed outside the required object scope.
- Length normalizes to metres, mass to kilograms; piece/set stay distinct.

Overlap precedence is deterministic: document index; explicit text identity;
cable section; diameter; pressure; voltage range; voltage scalar; mass; length;
count. Candidates sort by priority, longer span, start, kind and normalized value;
accepted slots finally sort by span/kind/value.

Stable warnings: `missing_slot_value`, `invalid_numeric_value`, `invalid_range`,
`ambiguous_diameter`, `ambiguous_cable_section`, `overlap_discarded`,
`multiple_family_values`. Stable conflicts: `conflicting_material`,
`conflicting_fire_class`, `conflicting_single_value`. Any warning/conflict sets
`requires_manual_review=True`; invalid/ambiguous text remains in the skeleton.

Skeleton placeholders use `<slot_kind>` in audit-span order. Document index is
removed without a placeholder. Remaining text passes through accepted Wave 1
canonicalization/ontology; audit, semantic and skeleton text remain separate.

## Handoff

Leave this card in `review` until orchestration accepts the result.
