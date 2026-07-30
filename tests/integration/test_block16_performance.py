"""Slow-only growth and deterministic export thresholds from the frozen manifest."""

from __future__ import annotations

import os
import time

import pytest
from report_processor.audit import AuditJournal, deterministic_bytes

from fixtures.audit.builders import run_inputs

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


def test_100k_journal_decision_appends_meet_growth_and_p95_limits(tmp_path) -> None:
    path = tmp_path / "audit.sqlite"
    with AuditJournal(path) as journal:
        run = journal.begin_run(*run_inputs(), nonce_hex="a" * 32)
        journal.append_event(run.run_id, "RUN", "PENDING")
        durations = []
        for attempt in range(1, 100_001):
            started = time.perf_counter()
            journal.append_event(run.run_id, "DATA", "DATA_COMMITTED", attempt_number=attempt)
            durations.append((time.perf_counter() - started) * 1000)
    assert path.stat().st_size / 100_000 <= 1024
    assert sorted(durations)[94_999] <= 25
