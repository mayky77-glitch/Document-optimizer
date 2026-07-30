"""Controlled, path-free presentation contract for drawing-card jobs."""

from __future__ import annotations

from .drawing_card_service import DrawingCardJob


def drawing_card_job_payload(job: DrawingCardJob) -> dict[str, object]:
    """Return only values safe to serialize through an admin endpoint."""
    review_required = job.status == "review_required"
    return {
        "job_id": job.job_id,
        "status": job.status,
        "summary": {
            "source_files": int(job.summary.get("source_files", len(job.sources))),
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
