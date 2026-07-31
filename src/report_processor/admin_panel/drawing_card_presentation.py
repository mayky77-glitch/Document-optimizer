"""Controlled, path-free presentation contract for drawing-card jobs."""

from __future__ import annotations

from collections.abc import Mapping

from report_processor.drawing_card.models import CATEGORY_DISPLAY_NAMES, CATEGORY_ORDER

from .drawing_card_service import DrawingCardJob


def drawing_card_job_payload(job: DrawingCardJob) -> dict[str, object]:
    """Return only values safe to serialize through an admin endpoint."""
    review_required = job.status == "review_required"
    source_files = job.summary.get("source_files")
    if source_files is None:
        source_files = len(job.sources)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "mode": job.mode,
        "period": job.period,
        "active_step": (
            "review" if review_required else "card" if job.result_available else "sources"
        ),
        "summary": {
            "source_files": int(source_files),
            "extracted_rows": int(job.summary.get("extracted_rows", 0)),
            "card_rows": int(job.summary.get("card_rows", 0)),
            "manual_review": int(job.summary.get("manual_review", 0)),
        },
        "warnings": list(job.warnings),
        "result_url": (
            f"/api/drawing-card/jobs/{job.job_id}/result" if job.result_available else None
        ),
        "review_url": f"/api/drawing-card/jobs/{job.job_id}/review" if review_required else None,
        "can_upload_review": review_required,
    }


def drawing_card_inline_review_payload(job: DrawingCardJob) -> dict[str, object]:
    """Return endpoint metadata without widening the stable job payload."""
    review_required = job.status == "review_required"
    return {
        "review_url": (
            f"/api/drawing-card/jobs/{job.job_id}/review/items" if review_required else None
        ),
        "can_apply": review_required and set(job.review_items) == set(job.inline_approvals),
    }


def drawing_card_category_options(job: DrawingCardJob) -> list[dict[str, str | None]]:
    """Return controlled category choices for the inline-review selector."""
    return [
        {
            "value": category.value,
            "label": CATEGORY_DISPLAY_NAMES[category],
            "target_unit": _first_category_unit(job.category_units, category.value),
        }
        for category in CATEGORY_ORDER
    ]


def drawing_card_inline_review_page(
    payload: Mapping[str, object], job: DrawingCardJob
) -> dict[str, object]:
    """Translate legacy row review data into the controlled public contract."""
    action_states = {
        "approve": "approved",
        "reject": "rejected",
        "cost_only": "cost_only",
        "change_category": "change_category",
        "quantity_only": "approved",
        "skip": "rejected",
    }
    categories = drawing_card_category_options(job)
    category_options = {str(item["value"]): item for item in categories}
    public_items = []
    for raw in payload.get("items", ()):
        if not isinstance(raw, Mapping):
            continue
        decision = raw.get("решение")
        action = decision.get("action") if isinstance(decision, Mapping) else None
        selected_category = decision.get("category") if isinstance(decision, Mapping) else None
        selected_option = category_options.get(str(selected_category))
        public_items.append(
            {
                "review_id": raw.get("review_id"),
                "work_name": raw.get("наименование"),
                "category": raw.get("предлагаемая_категория_id"),
                "category_label": raw.get("предлагаемая_категория_рус"),
                "proposed_category": raw.get("предлагаемая_категория_id"),
                "proposed_category_label": raw.get("предлагаемая_категория_рус"),
                "selected_category": selected_category,
                "selected_category_label": (
                    selected_option.get("label") if selected_option is not None else None
                ),
                "quantity": raw.get("количество"),
                "source_unit": raw.get("source_unit"),
                "target_unit": raw.get("target_unit"),
                "total_cost": raw.get("стоимость"),
                "confidence": raw.get("confidence"),
                "decision": action_states.get(str(action), "pending"),
            }
        )
    total = int(payload.get("total", len(public_items)))
    unresolved = int(payload.get("unresolved_count", total))
    return {
        "items": public_items,
        "page": payload.get("page", 1),
        "page_size": payload.get("page_size", 50),
        "total": total,
        "unresolved_count": unresolved,
        "can_apply": payload.get("can_apply", False),
        "categories": categories,
        "summary": {
            "Строк для проверки": total,
            "Осталось решений": unresolved,
        },
    }


def drawing_card_cluster_review_page(payload: Mapping[str, object]) -> dict[str, object]:
    """Expose both names during the additive transition to the cluster UI."""
    items = list(payload.get("items", ()))
    return {
        "items": items,
        "clusters": items,
        "page": payload.get("page", 1),
        "page_size": payload.get("page_size", 50),
        "total_clusters": payload.get("total_clusters", 0),
        "total_rows": payload.get("total_rows", 0),
        "unresolved_clusters": payload.get("unresolved_clusters", 0),
        "unresolved_rows": payload.get("unresolved_rows", 0),
        "can_apply": bool(payload.get("can_apply", False)),
    }


def _first_category_unit(category_units: dict[str, tuple[str, ...]], category: str) -> str | None:
    units = category_units.get(category, ())
    return units[0] if units else None
