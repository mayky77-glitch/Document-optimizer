---
type: task
status: done
work_id: reconciliation-wave1-remediation-v1
role: worker
agent_role: developer
owner: "wave1-remediation-packaging"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L1 compatibility profile maps to P3."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: "Runtime supplied inherited task execution; no separate launch confirmation was available."
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - "pyproject.toml"
source_paths:
  - "pyproject.toml"
depends_on: []
tags:
  - "task/implementation"
  - "status/review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 1 ontology wheel packaging

## Goal

Include `report_processor.work_semantics.resources/*.json` in built wheels using
the repository's existing package-data mechanism.

## Scope and instructions

- Modify only `write_scope` paths.
- Do not edit source/tests/lockfiles and do not perform Git operations.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `pyproject.toml` — added the existing setuptools package-data
  declaration for `report_processor.work_semantics` with `resources/*.json`.
- Commands and tests run: parsed `pyproject.toml` with `tomllib`; ran
  `uv build --wheel --out-dir <temporary directory>` and listed the wheel with
  `unzip -l`.
- Result: the built wheel contains
  `report_processor/work_semantics/resources/domain_ontology.json`.
- Risks or follow-up: setuptools emitted its existing deprecation warning for
  `project.license` as a TOML table; this task did not change license metadata.

## Handoff

Ready for orchestration review. No source, tests, lockfiles, or Git index/refs were changed.
