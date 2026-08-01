"""Strict request parsing for the future authoritative reconciliation routes."""

from __future__ import annotations

from collections.abc import Mapping

from report_processor.reconciliation_review import ReviewAction, ReviewDecision, ReviewMode


class ReconciliationReviewRequestError(ValueError):
    """Raised when an untrusted review request is outside the controlled contract."""


def parse_reconciliation_review_decision(payload: object) -> ReviewDecision:
    """Parse one accept/reject group or per-row decision without route coupling."""
    if not isinstance(payload, Mapping):
        raise ReconciliationReviewRequestError("Expected a JSON decision object")
    action = _enum(ReviewAction, payload.get("action"), "action")
    mode = _optional_enum(ReviewMode, payload.get("mode"), "mode")
    group_id = _optional_id(payload.get("group_id"), "group_id")
    row_id = _optional_id(payload.get("row_id"), "row_id")
    version = _optional_id(payload.get("version"), "version")
    category = _optional_category(payload.get("target_category"))
    try:
        return ReviewDecision(
            action=action,
            mode=mode,
            target_category=category,
            group_id=group_id,
            row_id=row_id,
            version=version,
        )
    except ValueError as error:
        raise ReconciliationReviewRequestError(str(error)) from error


def _enum(enum_type: type[ReviewAction] | type[ReviewMode], value: object, field: str):
    if not isinstance(value, str):
        raise ReconciliationReviewRequestError(f"{field} is required")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ReconciliationReviewRequestError(f"unsupported {field}") from error


def _optional_enum(enum_type: type[ReviewMode], value: object, field: str) -> ReviewMode | None:
    if value is None:
        return None
    return _enum(enum_type, value, field)


def _optional_id(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ReconciliationReviewRequestError(f"invalid {field}")
    return value.strip()


def _optional_category(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ReconciliationReviewRequestError("invalid target_category")
    return value.strip()
