"""Pure boundary for already-validated active-learning projections.

Actual Wave 4--7 runtime wiring is deliberately deferred to Wave 9.  This module
accepts only frozen core queue items and does not import their producing runtimes.
"""

from __future__ import annotations

from report_processor.reconciliation_patterns.active_learning import (
    ActiveLearningContractError,
    ActiveLearningQueue,
    ActiveLearningQueueItem,
)


def project_active_learning_queue(
    *,
    queue_ref: str,
    source_fingerprint_refs: tuple[str, ...],
    items: tuple[ActiveLearningQueueItem, ...],
) -> ActiveLearningQueue:
    """Project validated opaque items into the deterministic server-owned queue."""

    if not isinstance(items, tuple) or any(
        not isinstance(item, ActiveLearningQueueItem) for item in items
    ):
        raise ActiveLearningContractError("projection requires validated frozen queue items")
    return ActiveLearningQueue(queue_ref, source_fingerprint_refs, items)


__all__ = ["project_active_learning_queue"]
