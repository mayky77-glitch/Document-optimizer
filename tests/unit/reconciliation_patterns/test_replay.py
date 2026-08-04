"""Adversarial validators for immutable Wave 5 replay values."""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from report_processor.reconciliation_patterns import replay
from report_processor.reconciliation_patterns.pattern_models import PatternRegistryError


def _hash(letter: str) -> str:
    return "sha256:" + hashlib.sha256(letter.encode()).hexdigest()


def _snapshot(split: replay.ReplaySplit, letter: str) -> replay.ReplaySnapshotIdentity:
    values = {
        "split": split,
        "snapshot_ref": _hash(letter),
        "manifest_fingerprint": _hash(chr(ord(letter) + 1)),
        "corpus_fingerprint": _hash(chr(ord(letter) + 2)),
        "source_set_refs": (_hash(chr(ord(letter) + 3)),),
        "document_set_refs": (_hash(chr(ord(letter) + 4)),),
        "consequential_version_fingerprint": _hash("v"),
        "row_count": 3,
        "review_row_count": 2,
        "review_group_count": 1,
        "sealed": True,
        "seal_ref": _hash(chr(ord(letter) + 5)),
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    return replay.ReplaySnapshotIdentity(**values, fingerprint=replay.replay_fingerprint(values))


def test_ratio_uses_exact_cross_multiplication_and_zero_zero_is_undefined() -> None:
    assert replay.Ratio(0, 0).undefined
    assert replay.Ratio(2, 6).at_least(replay.Ratio(1, 3))
    assert not replay.Ratio(1, 4).at_least(replay.Ratio(1, 3))
    assert not replay.Ratio(0, 0).at_least(replay.Ratio(1, 3))
    with pytest.raises(PatternRegistryError) as error:
        replay.Ratio(1, 0)
    assert error.value.code == "REPLAY_SCHEMA_INVALID"


def test_fingerprints_seals_and_snapshot_boundaries_fail_closed() -> None:
    snapshot = _snapshot(replay.ReplaySplit.BASELINE, "a")
    assert snapshot.sealed and snapshot.review_row_count <= snapshot.row_count
    with pytest.raises(PatternRegistryError) as error:
        dataclasses.replace(snapshot, fingerprint=_hash("z"))
    assert error.value.code == "REPLAY_FINGERPRINT_MISMATCH"
    with pytest.raises(PatternRegistryError) as error:
        dataclasses.replace(snapshot, sealed=False)
    assert error.value.code == "SNAPSHOT_NOT_SEALED"


def test_measurements_and_percentiles_are_exact_and_closed() -> None:
    assert replay.nearest_rank((1, 2, 3, 4), 50) == 2
    assert replay.nearest_rank((1, 2, 3, 4), 95) == 4
    values = {
        "status": replay.MeasurementStatus.NOT_APPLICABLE,
        "environment_ref": None,
        "index_ref": None,
        "size_bytes": None,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    index = replay.IndexMeasurement(**values, fingerprint=replay.replay_fingerprint(values))
    measured_values = {
        "status": replay.MeasurementStatus.MEASURED,
        "environment_ref": _hash("environment"),
        "index_ref": _hash("index"),
        "size_bytes": 0,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    assert (
        replay.IndexMeasurement(
            **measured_values,
            fingerprint=replay.replay_fingerprint(measured_values),
        ).size_bytes
        == 0
    )
    measurements = {
        "latency_samples_ns": (2, 4),
        "p50_latency_ns": 2,
        "p95_latency_ns": 4,
        "index": index,
        "version": replay.GROUPING_REPLAY_VERSION,
    }
    assert (
        replay.ReplayMeasurements(
            **measurements, fingerprint=replay.replay_fingerprint(measurements)
        ).p95_latency_ns
        == 4
    )
    with pytest.raises(PatternRegistryError) as error:
        replay.nearest_rank((), 95)
    assert error.value.code == "MEASUREMENT_INVALID"
    incomplete = {**measured_values, "size_bytes": None}
    with pytest.raises(PatternRegistryError) as error:
        replay.IndexMeasurement(
            **incomplete,
            fingerprint=replay.replay_fingerprint(incomplete),
        )
    assert error.value.code == "MEASUREMENT_INVALID"


@pytest.mark.parametrize(
    "call",
    (
        lambda: replay.evaluate_shadow(object()),
        lambda: replay.owner_approval_ref(object(), object(), object()),
        lambda: replay.evaluate_promotion(object(), object(), object()),
    ),
)
def test_public_helpers_reject_malformed_types_with_domain_error(call: object) -> None:
    with pytest.raises(PatternRegistryError):
        call()  # type: ignore[operator]
