"""Bounded, reversible inline review state and private feedback records."""

from __future__ import annotations

import json
import os
import tempfile
from hashlib import sha256
from pathlib import Path

from ..matching.matcher import ReviewApproval
from ..models import CATEGORY_DISPLAY_NAMES, DrawingSourceRow, MatchDecision
from ..sources.normalization import normalize_text, normalize_unit

_ACTIONS = frozenset({"approve", "reject", "change_category", "quantity_only", "cost_only", "skip"})
_CATEGORY_ACTIONS = frozenset({"approve", "change_category", "quantity_only", "cost_only"})


def inline_review_rows(
    rows: list[DrawingSourceRow],
    decisions: list[MatchDecision],
    category_units: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, dict[str, object]]:
    """Presentation-safe Russian data; source paths, filenames and sheets stay private."""
    by_id = {row.row_id: row for row in rows}
    result: dict[str, dict[str, object]] = {}
    for decision in decisions:
        if not decision.requires_manual_review or decision.row_id not in by_id:
            continue
        row = by_id[decision.row_id]
        category_id = decision.category.value if decision.category else None
        confidence_values = [
            value
            for value in (decision.quantity_confidence, decision.cost_confidence)
            if value is not None
        ]
        result[decision.row_id] = {
            "review_id": decision.row_id,
            "наименование": row.work_name_raw or "",
            "единица": row.unit_raw,
            "source_unit": row.unit_raw,
            "target_unit": (
                ((category_units or {}).get(category_id) or (None,))[0] if category_id else None
            ),
            "количество": str(row.remaining_quantity)
            if row.remaining_quantity is not None
            else None,
            "стоимость": str(row.remaining_total_cost)
            if row.remaining_total_cost is not None
            else None,
            "предлагаемая_категория": category_id,
            "предлагаемая_категория_id": category_id,
            "предлагаемая_категория_рус": (
                CATEGORY_DISPLAY_NAMES[decision.category] if decision.category else None
            ),
            "причина": decision.reason[:240],
            "confidence": float(min(confidence_values)) if confidence_values else 0.0,
            "suggestion_ids": list(decision.evidence_ids[:5]),
        }
    return result


def review_approval(review_id: str, action: str, category: str | None) -> ReviewApproval:
    if action not in _ACTIONS:
        raise ValueError("unsupported inline review action")
    if action in _CATEGORY_ACTIONS and not category:
        raise ValueError("category is required for this inline review action")
    from ..models import TargetWorkCategory

    parsed = TargetWorkCategory(category) if category else None
    return ReviewApproval(review_id, action, parsed)


def write_approvals(path: Path, approvals: dict[str, ReviewApproval]) -> None:
    """Atomically write the fixed review schema; no caller payload is persisted."""
    payload = {
        review_id: {
            "row_id": approval.row_id,
            "action": approval.action,
            "category": approval.category.value if approval.category else None,
        }
        for review_id, approval in sorted(approvals.items())
    }
    _atomic_json(path, payload)


def append_feedback(
    path: Path,
    rows: dict[str, DrawingSourceRow],
    approvals: dict[str, ReviewApproval],
) -> None:
    """Persist only fixed classification memory, never file or workbook metadata."""
    records = _feedback_records(path)
    for review_id, approval in sorted(approvals.items()):
        row = rows.get(review_id)
        if row is None or approval.category is None or approval.action == "skip":
            continue
        source_text = normalize_text(row.work_name_raw)
        if not source_text:
            continue
        record = {
            "example_id": "feedback-"
            + sha256(
                f"{source_text}|{normalize_unit(row.unit_raw)}|{approval.category.value}".encode()
            ).hexdigest()[:20],
            "source_text": source_text,
            "normalized_text": source_text,
            "category": approval.category.value,
            "quantity_decision": "include"
            if approval.action in {"approve", "change_category", "quantity_only"}
            else "exclude",
            "cost_decision": "include"
            if approval.action in {"approve", "change_category", "cost_only"}
            else "exclude",
            "unit": normalize_unit(row.unit_raw),
            "source_type": None,
            "confirmed": True,
            "confirmed_by": "inline-review",
            "rule_version": "ReviewFeedbackStore-1.0",
        }
        records[(source_text, normalize_unit(row.unit_raw) or "")] = record
    if records:
        _atomic_text(
            path,
            "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                for _, record in sorted(records.items())
            ),
        )


def _feedback_records(path: Path) -> dict[tuple[str, str], dict[str, object]]:
    records: dict[tuple[str, str], dict[str, object]] = {}
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            key = (str(record["normalized_text"]), str(record.get("unit") or ""))
        except (KeyError, TypeError, json.JSONDecodeError):
            continue
        records[key] = record
    return records


def _atomic_json(path: Path, payload: object) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
