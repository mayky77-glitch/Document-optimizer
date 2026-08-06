"""Conserved, privacy-safe accounting for extracted drawing-card rows."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..models import DrawingCardRowDisposition, DrawingSourceRow, MatchDecision

DISPOSITION_MATCHED = "MATCHED"
DISPOSITION_MANUAL_REVIEW = "MANUAL_REVIEW"
DISPOSITION_HIERARCHY_AGGREGATE_EXCLUDED = "HIERARCHY_AGGREGATE_EXCLUDED"
DISPOSITION_HIERARCHY_RESOURCE_DETAIL_EXCLUDED = "HIERARCHY_RESOURCE_DETAIL_EXCLUDED"
DISPOSITION_UNCLASSIFIED = "UNCLASSIFIED"

_TERMINAL_DISPOSITIONS = frozenset(
    {
        DISPOSITION_MATCHED,
        DISPOSITION_MANUAL_REVIEW,
        DISPOSITION_HIERARCHY_AGGREGATE_EXCLUDED,
        DISPOSITION_HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
        DISPOSITION_UNCLASSIFIED,
    }
)
_EXCLUSION_DISPOSITIONS = frozenset(
    {
        DISPOSITION_HIERARCHY_AGGREGATE_EXCLUDED,
        DISPOSITION_HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
    }
)
MAX_EXCLUSION_SHARE = 0.50


def disposition_for_row(
    row: DrawingSourceRow,
    *,
    disposition: str,
    reason_code: str,
    rule_id: str | None = None,
    row_role: str = "work_item",
    hazard_flags: tuple[str, ...] = (),
) -> DrawingCardRowDisposition:
    """Build one audit record without persisting source paths or cell contents."""
    if disposition not in _TERMINAL_DISPOSITIONS:
        raise ValueError(f"Unsupported terminal disposition: {disposition}")
    if row_role not in {"aggregate", "resource_detail", "work_item", "unknown"}:
        raise ValueError(f"Unsupported row role: {row_role}")
    flags = tuple(dict.fromkeys((*_warning_codes(row.warnings), *hazard_flags)))
    return DrawingCardRowDisposition(
        row_id=row.row_id,
        disposition=disposition,
        reason_code=reason_code,
        rule_id=rule_id,
        file_id=row.location.file_id,
        safe_basename=Path(row.location.filename).name,
        sheet_name=row.location.sheet_name,
        row_number=row.location.row_number,
        position_code=row.position_code_raw,
        row_role=row_role,
        hazard_flags=flags,
    )


def disposition_for_decision(
    row: DrawingSourceRow, decision: MatchDecision
) -> DrawingCardRowDisposition:
    """Account for a matcher outcome; a review wins over a nominal category."""
    hazard_flags = (*_warning_codes(decision.warnings), decision.status)
    if decision.requires_manual_review:
        return disposition_for_row(
            row,
            disposition=DISPOSITION_MANUAL_REVIEW,
            reason_code="MATCH_REQUIRES_MANUAL_REVIEW",
            rule_id=_decision_rule_id(decision),
            hazard_flags=hazard_flags,
        )
    if decision.category is not None:
        return disposition_for_row(
            row,
            disposition=DISPOSITION_MATCHED,
            reason_code="MATCHED_CATEGORY",
            rule_id=_decision_rule_id(decision),
            hazard_flags=hazard_flags,
        )
    return disposition_for_row(
        row,
        disposition=DISPOSITION_UNCLASSIFIED,
        reason_code="NO_MATCHING_CATEGORY",
        rule_id=_decision_rule_id(decision),
        row_role="unknown" if not _has_role_policy(row) else "work_item",
        hazard_flags=hazard_flags,
    )


def funnel_summary(
    dispositions: list[DrawingCardRowDisposition], *, extracted_row_count: int
) -> dict[str, object]:
    """Return conserved counts and strict blocker codes for funnel anomalies."""
    counts = Counter(record.disposition for record in dispositions)
    for disposition in (*sorted(_TERMINAL_DISPOSITIONS), "DUPLICATE_EXCLUDED"):
        counts.setdefault(disposition, 0)
    blockers: list[str] = []
    if len(dispositions) != extracted_row_count:
        blockers.append("FUNNEL_CONSERVATION_FAILED")
    if any(record.disposition not in _TERMINAL_DISPOSITIONS for record in dispositions):
        blockers.append("FUNNEL_UNKNOWN_DISPOSITION")
    if any(record.row_role == "unknown" for record in dispositions):
        blockers.append("FUNNEL_UNKNOWN_ROLE_POLICY")
    excluded = sum(counts[disposition] for disposition in _EXCLUSION_DISPOSITIONS)
    exclusion_share = excluded / extracted_row_count if extracted_row_count else 0.0
    if extracted_row_count and exclusion_share > MAX_EXCLUSION_SHARE:
        blockers.append("FUNNEL_ANOMALOUS_EXCLUSION_SHARE")
    return {
        "extracted_rows": extracted_row_count,
        "terminal_dispositions": len(dispositions),
        "disposition_counts": dict(sorted(counts.items())),
        "unclassified_count": counts[DISPOSITION_UNCLASSIFIED],
        "excluded_count": excluded,
        "exclusion_share": exclusion_share,
        "strict_blockers": blockers,
    }


def _decision_rule_id(decision: MatchDecision) -> str | None:
    return decision.quantity_rule_id or decision.cost_rule_id


def _warning_codes(warnings: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(warning).partition(":")[0] for warning in warnings)


def _has_role_policy(row: DrawingSourceRow) -> bool:
    return bool(
        row.position_code_raw
        or row.cost_type_code_raw
        or row.work_name_raw
        or row.unit_raw
        or row.remaining_quantity is not None
        or row.remaining_total_cost is not None
    )
