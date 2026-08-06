---
type: task
status: frozen
card_id: drawing-card-ux-wave3-service-core
version: 1
supersedes: null
work_id: drawing-card-ux-wave3-service-v1
task_id: service-core
purpose: Persist complete row and packet feedback atomically before rerun and wire strict packets, scope, recovery and metrics.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave3-service-core.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 99fbf75fa9d0bca9026b78b07edb7bd6a56df32d
branch: codex/drawing-card-ux-wave3-service-core
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/drawing_card/models.py
  - src/report_processor/drawing_card/workflow.py
  - src/report_processor/drawing_card/review/feedback.py
  - src/report_processor/drawing_card/review/context.py
  - src/report_processor/drawing_card/review/inline.py
  - tests/unit/admin_panel/test_drawing_card_service.py
  - tests/unit/drawing_card/test_feedback_store.py
  - tests/unit/drawing_card/test_feedback_replay.py
  - tests/unit/drawing_card/test_inline_review_flow.py
  - tests/integration/test_drawing_card_feedback_lifecycle.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/drawing_card_review_payload.py
  - src/report_processor/admin_panel/drawing_card_presentation.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/drawing_card/review/clusters.py
  - src/report_processor/drawing_card/audit/review_metrics.py
  - knowledge
  - docs
contract_versions:
  input: DrawingCardExactReplay-1.0
  output: DrawingCardReviewServiceCore-3.0
acceptance_commands:
  - uv run pytest -q tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_feedback_store.py tests/unit/drawing_card/test_feedback_replay.py tests/unit/drawing_card/test_inline_review_flow.py tests/integration/test_drawing_card_feedback_lifecycle.py
  - uv run ruff check src/report_processor/admin_panel/drawing_card_service.py src/report_processor/drawing_card/models.py src/report_processor/drawing_card/workflow.py src/report_processor/drawing_card/review/feedback.py src/report_processor/drawing_card/review/context.py src/report_processor/drawing_card/review/inline.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_feedback_store.py tests/unit/drawing_card/test_feedback_replay.py tests/unit/drawing_card/test_inline_review_flow.py tests/integration/test_drawing_card_feedback_lifecycle.py
  - uv run ruff format --check src/report_processor/admin_panel/drawing_card_service.py src/report_processor/drawing_card/models.py src/report_processor/drawing_card/workflow.py src/report_processor/drawing_card/review/feedback.py src/report_processor/drawing_card/review/context.py src/report_processor/drawing_card/review/inline.py tests/unit/admin_panel/test_drawing_card_service.py tests/unit/drawing_card/test_feedback_store.py tests/unit/drawing_card/test_feedback_replay.py tests/unit/drawing_card/test_inline_review_flow.py tests/integration/test_drawing_card_feedback_lifecycle.py
  - git diff --check
---

# Review service core

Add explicit validated tenant scope (local default), deterministic order-insensitive project ID from
immutable source hashes plus existing-card hash, model/rules versions, feedback input hashes and
primitive review metrics to `DrawingCardJob`; persist and strictly restore them in the private
manifest. Keep the internal result path unchanged. The service must pass `feedback_store`, scope,
versions and hashes to `WorkflowRequest` and must never pass legacy `feedback_examples`.

Extend the not-yet-released `DrawingCardFeedback-2.0` event additively with the reviewer-selected
quantity and cost resolutions. The exact context `unit_policy` describes the original candidate
decisions, including `review`; the selected resolutions describe the saved outcome. Existing
unambiguous entries stay readable. Build contexts for every named manual candidate, including absent
proposed category/position through controlled sentinels. Replay confirmation only from explicit safe
resolutions; `reject`/`exclude` remains both-excluded. Never replay a formula/Excel hazard.

`apply_inline_review` must construct a membership-complete page containing one event for every row
and one packet event for each still-current applicable packet action, then call one
`FeedbackStore.append_page` before writing/scheduling the rerun. Use deterministic event IDs and a
stable review-generation timestamp so retries are idempotent. If feedback, decisions, or manifest
persistence fails, do not call the runner; keep decisions retryable. Retain original extracted rows
and link audit entries through opaque member IDs. A rerun error increments post-review errors.

Always call `build_review_clusters(..., contexts=complete_contexts)`. Context equality must cover
tenant/project, normalized work, source type, exact reason, proposed category, match mode, unit
compatibility class, transactional role, rules version and original quantity/cost modes. Hazards and
incomplete context are singleton. `UNIT_MISMATCH` packets require identical resolution modes;
multiple-category rows require exact normalized work, never embedding-only similarity.

Public service contracts frozen for the parallel API task:

- `list_review_clusters(job_id, page=1, page_size=50, reason=None, category=None,
  safe_filename=None, confidence=None, only_unresolved=True)`;
- `get_review_context(job_id, review_id, radius=2)` returns bounded adjacent safe row objects;
- `put_review_item(..., version=None)` rejects a supplied stale membership version;
- the cluster-page dict includes `review_categories` (`id`, Russian `label`, `units`) and
  `review_metrics` primitives.

Persist unique opened cluster IDs and counters for candidates, queued rows, packets, singletons,
feedback hits, exclusions, overrides, applies and post-review errors. Tests must cover atomic page
failure before rerun, retry idempotency, tenant isolation, contract/rule invalidation, hazard
visibility, packet audit membership, strict grouping, restart recovery and metric stability.
