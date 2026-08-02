from __future__ import annotations

import time
from decimal import Decimal

from report_processor.reconciliation_grouping.features import extract_features
from report_processor.reconciliation_grouping.models import GroupInput, PackageVersionContext
from report_processor.reconciliation_grouping.packages import (
    build_reconciliation_packages,
    rank_with_local_assist,
)
from report_processor.reconciliation_grouping.semantic_model import (
    LocalSemanticAssist,
    VersionedEmbeddingCache,
)
from report_processor.reconciliation_review.models import ReviewGroup, ReviewMode, ReviewRow


def _feature():
    row = ReviewRow(
        row_id="row-a",
        display_name="Монтаж силового кабеля",
        unit="м",
        quantity=Decimal("1"),
        cost=Decimal("2"),
        proposed_category="Кабельные работы",
    )
    group = ReviewGroup(
        group_id="group-a",
        version="version-a",
        normalized_name="монтаж силового кабеля",
        normalized_unit="м",
        member_ids=("row-a",),
        proposed_category="Кабельные работы",
    )
    return extract_features(GroupInput(group, (row,), ReviewMode.QUANTITY_COST)), row, group


def _context() -> PackageVersionContext:
    return PackageVersionContext(("source-digest-a",), "target-digest-a", "catalog-v1")


class _TimeoutEncoder:
    def encode(self, texts: tuple[str, ...]):
        time.sleep(0.05)
        return tuple((1.0, 0.0) for _ in texts)


class _BrokenEncoder:
    def encode(self, texts: tuple[str, ...]):
        raise RuntimeError("missing local model")


def test_local_assist_times_out_and_errors_without_affecting_deterministic_packages() -> None:
    feature, row, group = _feature()
    baseline = build_reconciliation_packages((row,), (group,), version_context=_context())

    timeout = LocalSemanticAssist(
        _TimeoutEncoder(), model_revision="local-r1", timeout_seconds=0.001
    )
    broken = LocalSemanticAssist(_BrokenEncoder(), model_revision="local-r1")

    assert timeout.rank((feature,)).unavailable_reason == "local_model_timeout"
    assert broken.rank((feature,)).unavailable_reason == "local_model_unavailable"
    assert (
        build_reconciliation_packages((row,), (group,), version_context=_context()).packages
        == baseline.packages
    )


def test_cache_is_reused_only_inside_the_same_strict_version_boundary() -> None:
    feature, _row, _group = _feature()
    cache = VersionedEmbeddingCache()
    cache.put(feature, model_revision="local-r1", vector=(1.0, 0.0))

    assert cache.get(feature, model_revision="local-r1") == (1.0, 0.0)
    assert cache.get(feature, model_revision="local-r2") is None
    assert (
        rank_with_local_assist(
            build_reconciliation_packages((_row,), (_group,), version_context=_context()), None
        ).unavailable_reason
        == "local_model_not_configured"
    )


def test_local_assist_uses_bounded_batches() -> None:
    feature, _row, _group = _feature()

    class BatchEncoder:
        def __init__(self) -> None:
            self.sizes: list[int] = []

        def encode(self, texts: tuple[str, ...]):
            self.sizes.append(len(texts))
            return tuple((1.0, 0.0) for _ in texts)

    encoder = BatchEncoder()
    assist = LocalSemanticAssist(encoder, model_revision="local-r1", batch_size=1)

    assert assist.rank((feature, feature)).similarities
    assert encoder.sizes == [1]
