"""Combine independent name and content signals without hiding conflicts."""

from __future__ import annotations

from report_processor.excel import DualWorkbookSession
from report_processor.schema.config import SchemaDetectionConfig
from report_processor.schema.models import (
    SheetClassification,
    SheetType,
    SheetTypeCandidate,
    WorksheetScanWindow,
)
from report_processor.schema.scan_window import scan_worksheet_window
from report_processor.schema.sheet_content_classifier import classify_scan_content
from report_processor.schema.sheet_name_classifier import classify_sheet_name


def _score_map(candidates: tuple[SheetTypeCandidate, ...]) -> dict[SheetType, float]:
    return {candidate.sheet_type: candidate.score for candidate in candidates}


def _markers(candidate: SheetTypeCandidate | None, prefix: str) -> tuple[str, ...]:
    if candidate is None:
        return ()
    return tuple(
        reason.removeprefix(prefix) for reason in candidate.reasons if reason.startswith(prefix)
    )


def _combined_candidates(
    name_candidates: tuple[SheetTypeCandidate, ...],
    content_candidates: tuple[SheetTypeCandidate, ...],
) -> tuple[SheetTypeCandidate, ...]:
    name_scores = _score_map(name_candidates)
    content_scores = _score_map(content_candidates)
    all_types = set(name_scores) | set(content_scores)
    combined: list[SheetTypeCandidate] = []
    for sheet_type in all_types:
        name_score = name_scores.get(sheet_type, 0.0)
        content_score = content_scores.get(sheet_type, 0.0)
        if name_score and content_score:
            score = 0.45 * name_score + 0.55 * content_score
        elif name_score:
            score = 0.85 * name_score
        else:
            score = 0.90 * content_score
        reasons = (
            f"combined:name={name_score:.3f}",
            f"combined:content={content_score:.3f}",
        )
        combined.append(SheetTypeCandidate(sheet_type, round(score, 4), reasons))
    return tuple(sorted(combined, key=lambda item: (-item.score, item.sheet_type.value)))


def classify_worksheet(
    session: DualWorkbookSession,
    sheet_name: str,
    config: SchemaDetectionConfig,
    *,
    scan: WorksheetScanWindow | None = None,
) -> SheetClassification:
    scan = scan or scan_worksheet_window(session, sheet_name, config.scan)
    name_candidates = classify_sheet_name(sheet_name)
    content_candidates = classify_scan_content(scan, config.sheet_signatures)
    combined = _combined_candidates(name_candidates, content_candidates)

    name_top = name_candidates[0] if name_candidates else None
    content_top = content_candidates[0] if content_candidates else None
    conflict = (
        name_top is not None
        and content_top is not None
        and name_top.sheet_type != content_top.sheet_type
        and name_top.score >= 0.72
        and content_top.score >= 0.62
    )

    if not combined or combined[0].score < 0.28:
        selected_type = SheetType.UNKNOWN
        confidence = combined[0].score if combined else 0.0
        status = "UNKNOWN_SHEET_TYPE"
    else:
        selected_type = combined[0].sheet_type
        confidence = combined[0].score
        if conflict:
            status = "AMBIGUOUS_SHEET_TYPE"
            confidence = max(name_top.score, content_top.score)
        elif confidence < config.min_sheet_confidence:
            status = "LOW_CONFIDENCE_SHEET_TYPE"
        else:
            status = "OK"

    selected_name = next(
        (item for item in name_candidates if item.sheet_type == selected_type),
        None,
    )
    selected_content = next(
        (item for item in content_candidates if item.sheet_type == selected_type),
        None,
    )
    warnings: list[str] = []
    if conflict and name_top and content_top:
        warnings.append(
            f"SHEET_TYPE_CONFLICT:{name_top.sheet_type.value}:{content_top.sheet_type.value}"
        )
    return SheetClassification(
        sheet_name=sheet_name,
        sheet_type=selected_type,
        confidence=round(min(max(confidence, 0.0), 1.0), 4),
        name_score=selected_name.score if selected_name else 0.0,
        content_score=selected_content.score if selected_content else 0.0,
        matched_name_markers=_markers(selected_name, "name:"),
        matched_content_markers=tuple(
            reason.split(":", 2)[-1]
            for reason in (selected_content.reasons if selected_content else ())
            if reason.startswith("content:") and ":negative:" not in reason
        ),
        alternative_types=combined[:5],
        status=status,
        warnings=tuple(warnings),
    )
