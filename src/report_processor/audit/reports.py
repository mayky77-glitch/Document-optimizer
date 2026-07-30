"""Privacy-safe report builders; trace reports contain identities only."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .models import AuditEvent, AuditRun, RunReport, TraceReport
from .serialization import redact

_TRACE_KEYS = frozenset(
    {"write_id", "calculation_id", "trace_id", "match_result_id", "candidate_id", "source_row_id"}
)


def run_report(run: AuditRun, events: Iterable[AuditEvent]) -> RunReport:
    items = tuple(events)
    return RunReport(
        run.run_id,
        run.run_key,
        items[-1].controlled_state_code if items else "PENDING",
        len(items),
        tuple(
            sorted({item.controlled_warning_code for item in items if item.controlled_warning_code})
        ),
        (),
    )


def trace_report(run_id: str, links: Iterable[Mapping[str, object]]) -> TraceReport:
    result = []
    for link in links:
        if not set(link).issubset(_TRACE_KEYS):
            raise ValueError("trace report accepts IDs only")
        result.append(redact(link))
    return TraceReport(
        run_id,
        tuple(
            sorted(
                result,
                key=lambda item: tuple(str(item.get(key, "")) for key in sorted(_TRACE_KEYS)),
            )
        ),
    )
