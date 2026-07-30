---
type: task
status: done
work_id: confirmed-fixes-20260730
role: worker
agent_role: worker
owner: "devops-tooling"
profile: L1
routing_grade: P3
progress_revision: 2
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
fallback_reason: "Worker runtime inherited the assigned P3 Terra/medium route; no per-child override is available in this task context."
model_fallback: false
last_verified: 2026-07-30
updated: 2026-07-30
write_scope:
  - "scripts/setup_mac_linux.sh"
  - "scripts/setup_windows.ps1"
  - "requirements-dev.txt"
  - "pyproject.toml"
  - "README.md"
source_paths:
  - "scripts/setup_mac_linux.sh"
  - "scripts/setup_windows.ps1"
  - "requirements-dev.txt"
  - "pyproject.toml"
  - "README.md"
depends_on: []
tags:
  - "task/implementation"
  - "status/done"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Developer setup and checks

## Goal

Set up the developer checks (`pytest` and `ruff`) together with the runtime
dependencies on macOS/Linux and Windows, and document how to run them.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Route: P3 -> devops-tooling / gpt-5.6-terra / medium. Actual execution is
  inherited as recorded in the front matter.
- Changed paths: `scripts/setup_mac_linux.sh`, `scripts/setup_windows.ps1`,
  `README.md`, and this task card.
- Commands and tests run: `bash -n scripts/setup_mac_linux.sh`; Python
  `tomllib` parse of `pyproject.toml`; static PowerShell content validation.
- Result: both setup scripts install the existing `requirements-dev.txt`, which
  includes runtime dependencies plus `pytest` and `ruff`; each prints the two
  developer-check commands. README matches. `pwsh` is unavailable, so a native
  PowerShell parser check was not run.
- Risks or follow-up: no dependency versions changed. A Windows host should run
  `scripts/setup_windows.ps1` once to confirm the local Python launcher and
  execution-policy environment.

## Proposed knowledge delta

None. The change is self-contained developer tooling; no component card is
needed.

## Handoff

Leave this card in `review` until orchestration accepts the result.
