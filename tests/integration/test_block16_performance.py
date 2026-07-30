"""Slow-only growth and deterministic export thresholds from the frozen manifest."""

from __future__ import annotations

import os
import time

import pytest
from report_processor.audit import deterministic_bytes

pytestmark = pytest.mark.skipif(os.getenv("RUN_SLOW") != "1", reason="set RUN_SLOW=1")


def test_deterministic_export_of_100k_decisions_meets_p95_threshold() -> None:
    rows = tuple(
        {"run_id": f"r-{item:06d}", "event_sequence": item, "count": item}
        for item in range(100_000)
    )
    samples = []
    for _ in range(5):
        started = time.perf_counter()
        payload = deterministic_bytes(reversed(rows), "jsonl")
        samples.append((time.perf_counter() - started) * 1000)
    assert payload and sorted(samples)[4] <= 5000
