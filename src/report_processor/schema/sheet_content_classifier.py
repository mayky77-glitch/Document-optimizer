"""Content-based sheet classification over an already bounded scan window."""

from __future__ import annotations

from report_processor.excel import DualWorkbookSession
from report_processor.schema.config import SheetScanConfig
from report_processor.schema.models import (
    SheetTypeCandidate,
    SheetTypeSignature,
    WorksheetScanWindow,
)
from report_processor.schema.scan_window import scan_worksheet_window


def _scan_corpus(scan: WorksheetScanWindow) -> str:
    values = [
        cell.normalized_text for cell in scan.cells if cell.normalized_text and not cell.is_formula
    ]
    return " | ".join(values)


def classify_scan_content(
    scan: WorksheetScanWindow,
    signatures: tuple[SheetTypeSignature, ...],
) -> tuple[SheetTypeCandidate, ...]:
    corpus = _scan_corpus(scan)
    candidates: list[SheetTypeCandidate] = []
    for signature in signatures:
        strong = tuple(marker for marker in signature.strong_markers if marker in corpus)
        weak = tuple(marker for marker in signature.weak_markers if marker in corpus)
        negative = tuple(marker for marker in signature.negative_markers if marker in corpus)
        score = min(len(strong) * 0.34, 0.68) + min(len(weak) * 0.08, 0.32)
        score -= min(len(negative) * 0.18, 0.45)
        if not strong:
            score = min(score, 0.58)
        score = round(min(max(score, 0.0), 1.0), 4)
        if score < max(signature.min_score * 0.55, 0.12):
            continue
        reasons = (
            *(f"content:strong:{item}" for item in strong),
            *(f"content:weak:{item}" for item in weak),
            *(f"content:negative:{item}" for item in negative),
        )
        candidates.append(SheetTypeCandidate(signature.sheet_type, score, reasons))
    return tuple(sorted(candidates, key=lambda item: (-item.score, item.sheet_type.value)))


def classify_sheet_content(
    session: DualWorkbookSession,
    sheet_name: str,
    scan_config: SheetScanConfig,
    signatures: tuple[SheetTypeSignature, ...] = (),
) -> tuple[SheetTypeCandidate, ...]:
    if not signatures:
        from report_processor.schema.signatures import DEFAULT_SHEET_SIGNATURES

        signatures = DEFAULT_SHEET_SIGNATURES
    scan = scan_worksheet_window(session, sheet_name, scan_config)
    return classify_scan_content(scan, signatures)
