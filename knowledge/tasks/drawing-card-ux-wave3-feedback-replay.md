---
type: task
status: frozen
card_id: drawing-card-ux-wave3-feedback-replay
version: 1
supersedes: null
work_id: drawing-card-ux-wave3-integration-v1
task_id: feedback-replay
purpose: Apply only exact, version-valid, hazard-free feedback after normal matching and before manual queue formation.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave3-feedback-replay.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - cfa3b830555313162f7c80b1182bd79d8065f983
branch: codex/drawing-card-ux-wave3-feedback-replay
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/models.py
  - src/report_processor/drawing_card/workflow.py
  - src/report_processor/drawing_card/review/context.py
  - src/report_processor/drawing_card/review/__init__.py
  - tests/unit/drawing_card/test_feedback_replay.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/drawing_card/review/feedback.py
  - src/report_processor/drawing_card/review/clusters.py
  - src/report_processor/drawing_card/audit/review_metrics.py
  - knowledge
  - docs
contract_versions:
  input: DrawingCardFeedback-2.0
  output: DrawingCardExactReplay-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/drawing_card/test_feedback_store.py tests/unit/drawing_card/test_feedback_replay.py tests/unit/drawing_card/test_workflow_funnel.py
  - uv run ruff check src/report_processor/drawing_card/models.py src/report_processor/drawing_card/workflow.py src/report_processor/drawing_card/review/context.py src/report_processor/drawing_card/review/__init__.py tests/unit/drawing_card/test_feedback_replay.py
  - uv run ruff format --check src/report_processor/drawing_card/models.py src/report_processor/drawing_card/workflow.py src/report_processor/drawing_card/review/context.py src/report_processor/drawing_card/review/__init__.py tests/unit/drawing_card/test_feedback_replay.py
  - git diff --check
---

# Exact feedback replay

Keep the normal deterministic matcher authoritative. Only after it creates a manual-review
candidate, build a complete `FeedbackContext` and perform `FeedbackStore.lookup_exact`.
The lookup must include explicit tenant/project scope, normalized work and fingerprint,
contract position, original proposed category, normalized source unit, match mode, original
quantity/cost policy, immutable input hashes, model/rules versions, subject and exact member IDs.

Apply a hit only when the ledger entry is active and hazard-free. `confirm`/`reclassify` produce a
non-review decision with the saved category; `reject`/`exclude` produce an explicit excluded
decision. Preserve the ledger event ID as evidence and identify the strategy as exact feedback
replay. Similar text, stale hashes/versions, changed scope/category/position/unit/mode/policy and any
formula/Excel hazard must remain visible in manual review. Legacy `ReviewFeedbackStore-1.0` must
not be loaded by this workflow contract.

Expose primitive review metrics on `WorkflowResult`: candidates before replay, exact feedback
hits and queued review rows. Tests must prove exact hit, every invalidation dimension, tenant
isolation, hazard visibility, no similar-text replay and preserved row disposition accounting.
