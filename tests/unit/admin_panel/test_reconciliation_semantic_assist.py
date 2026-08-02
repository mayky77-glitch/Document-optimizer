from __future__ import annotations

import os
import time
from decimal import Decimal

import pytest

from report_processor.admin_panel.reconciliation_semantic_assist import (
    CONTROLLED_SEMANTIC_HINT,
    LOCAL_ASSIST_TIMEOUT_SECONDS,
    MAX_AMBIGUOUS_GROUPS,
    RUBERT_TINY2_MODEL_REVISION,
    run_local_semantic_assist,
)
from report_processor.reconciliation_grouping import (
    PackageVersionContext,
    build_reconciliation_packages,
)
from report_processor.reconciliation_review import ReviewRow, build_review_groups
from report_processor.stage_rag.encoder import RuBERTTiny2Encoder


def _grouping(count: int = 1):
    rows = tuple(
        ReviewRow(
            f"row-{index}",
            f"Неизвестная работа {index}",
            "м",
            Decimal("1"),
            Decimal("2"),
            "target-1",
        )
        for index in range(count)
    )
    groups = build_review_groups(rows)
    return build_reconciliation_packages(
        rows,
        groups,
        version_context=PackageVersionContext(
            ("source",), "target", "catalog", model_revision=RUBERT_TINY2_MODEL_REVISION
        ),
    )


class _AvailableEncoder:
    def __init__(self) -> None:
        self.batches: list[tuple[str, ...]] = []

    def encode(self, texts: tuple[str, ...]):
        self.batches.append(texts)
        return tuple((1.0, 0.0) for _ in texts)


class _BrokenEncoder:
    def encode(self, texts: tuple[str, ...]):
        raise RuntimeError("private local failure")


class _SlowEncoder:
    def encode(self, texts: tuple[str, ...]):
        time.sleep(0.05)
        return tuple((1.0, 0.0) for _ in texts)


class _InvalidEncoder:
    def encode(self, texts: tuple[str, ...]):
        return ()


def test_assist_uses_one_deterministic_bounded_batch_without_mutating_grouping() -> None:
    grouping = _grouping(MAX_AMBIGUOUS_GROUPS + 2)
    baseline = (grouping.packages, grouping.families, grouping.exceptions)
    encoder = _AvailableEncoder()

    snapshot = run_local_semantic_assist(grouping, encoder=encoder)

    assert len(encoder.batches) == 1
    assert len(encoder.batches[0]) == MAX_AMBIGUOUS_GROUPS
    assert snapshot.hint == CONTROLLED_SEMANTIC_HINT
    assert snapshot.group_ids == tuple(sorted(snapshot.group_ids))
    assert (grouping.packages, grouping.families, grouping.exceptions) == baseline


def test_assist_requires_comparable_results_before_exposing_a_hint() -> None:
    grouping = _grouping()

    snapshot = run_local_semantic_assist(grouping, encoder=_AvailableEncoder())

    assert snapshot == type(snapshot)()


def test_available_and_unavailable_assist_keep_exact_versioned_packages_identical() -> None:
    available_grouping = _grouping(2)
    unavailable_grouping = _grouping(2)

    available = run_local_semantic_assist(available_grouping, encoder=_AvailableEncoder())
    unavailable = run_local_semantic_assist(unavailable_grouping, encoder=_BrokenEncoder())

    assert available.hint == CONTROLLED_SEMANTIC_HINT
    assert unavailable.hint is None
    assert available_grouping.packages == unavailable_grouping.packages
    assert available_grouping.families == unavailable_grouping.families


def test_default_timeout_allows_one_bounded_cold_local_batch(monkeypatch) -> None:
    grouping = _grouping(2)
    captured: dict[str, object] = {}

    class RecordingAssist:
        def __init__(self, _encoder, **kwargs) -> None:
            captured.update(kwargs)

        def rank(self, _features):
            return type(
                "Result", (), {"unavailable_reason": None, "similarities": (("a", "b", 1.0),)}
            )()

    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_semantic_assist.LocalSemanticAssist",
        RecordingAssist,
    )

    run_local_semantic_assist(grouping, encoder=_AvailableEncoder())

    assert captured == {
        "model_revision": RUBERT_TINY2_MODEL_REVISION,
        "timeout_seconds": LOCAL_ASSIST_TIMEOUT_SECONDS,
        "batch_size": 2,
    }


@pytest.mark.parametrize("encoder", (_BrokenEncoder(), _InvalidEncoder(), _SlowEncoder()))
def test_assist_failure_is_private_and_grouping_remains_identical(encoder) -> None:
    grouping = _grouping()
    baseline = (grouping.packages, grouping.families, grouping.exceptions)

    snapshot = run_local_semantic_assist(grouping, encoder=encoder, timeout_seconds=0.001)

    assert snapshot.group_ids == () and snapshot.hint is None
    assert (grouping.packages, grouping.families, grouping.exceptions) == baseline
    assert "private" not in repr(snapshot)
    assert "timeout" not in repr(snapshot)


@pytest.mark.skipif(os.getenv("RUN_RAG_MODEL") != "1", reason="set RUN_RAG_MODEL=1")
def test_pinned_local_encoder_smoke_produces_embeddings_without_a_download() -> None:
    encoder = RuBERTTiny2Encoder()

    vectors = encoder.encode(("Монтаж силового кабеля",))

    assert RUBERT_TINY2_MODEL_REVISION
    assert len(vectors) == 1 and len(vectors[0]) > 0
