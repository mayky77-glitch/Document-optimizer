"""Strict request parsing for the future authoritative reconciliation routes."""

from __future__ import annotations

from collections.abc import Mapping

from report_processor.reconciliation_review import ReviewAction, ReviewDecision, ReviewMode

from .reconciliation_state import BatchReviewDecision


class ReconciliationReviewRequestError(ValueError):
    """Raised when an untrusted review request is outside the controlled contract."""


def parse_reconciliation_review_decision(
    payload: object, *, group_id: str | None = None, row_id: str | None = None
) -> ReviewDecision:
    """Parse one accept/reject group or per-row decision without route coupling."""
    if not isinstance(payload, Mapping):
        raise ReconciliationReviewRequestError("Expected a JSON decision object")
    action = _enum(ReviewAction, payload.get("action"), "action")
    mode = _optional_enum(ReviewMode, payload.get("mode"), "mode")
    body_group_id = _optional_id(payload.get("group_id"), "group_id")
    body_row_id = _optional_id(payload.get("row_id"), "row_id")
    if group_id is not None and body_group_id not in {None, group_id}:
        raise ReconciliationReviewRequestError("group_id does not match route")
    if row_id is not None and body_row_id not in {None, row_id}:
        raise ReconciliationReviewRequestError("row_id does not match route")
    group_id = group_id or body_group_id
    row_id = row_id or body_row_id
    version = _optional_id(payload.get("version"), "version")
    category = _optional_category(payload.get("category_id"))
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


def parse_reconciliation_batch_decision(payload: object) -> BatchReviewDecision:
    """Parse a package/family decision without accepting route-unrelated facts."""
    if not isinstance(payload, Mapping):
        raise ReconciliationReviewRequestError("Expected a JSON decision object")
    try:
        return BatchReviewDecision(
            action=_enum(ReviewAction, payload.get("action"), "action"),
            mode=_optional_enum(ReviewMode, payload.get("mode"), "mode"),
            target_category=_optional_category(payload.get("category_id")),
            version=_optional_id(payload.get("version"), "version"),
        )
    except ValueError as error:
        raise ReconciliationReviewRequestError(str(error)) from error


def parse_safe_package_ids(payload: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("packages"), list):
        raise ReconciliationReviewRequestError("packages are required")
    values: list[tuple[str, str]] = []
    for value in payload["packages"]:
        if not isinstance(value, Mapping):
            raise ReconciliationReviewRequestError("invalid package")
        package_id = _optional_id(value.get("package_id"), "package_id")
        version = _optional_id(value.get("version"), "version")
        if package_id is None or version is None:
            raise ReconciliationReviewRequestError("package_id and version are required")
        values.append((package_id, version))
    if not values or len({item[0] for item in values}) != len(values):
        raise ReconciliationReviewRequestError("packages must be unique and non-empty")
    return tuple(values)


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
        raise ReconciliationReviewRequestError("invalid category_id")
    return value.strip()
