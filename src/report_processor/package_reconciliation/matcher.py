"""Fail-closed matching of extracted workbook rows to AОСР evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import PurePosixPath

from .models import WorkbookRowFact
from .pdf_documents import MIN_OCR_CONFIDENCE, PdfDocumentEvidence

STATUSES = frozenset({"MATCH", "MISMATCH", "AMBIGUOUS", "NO_EVIDENCE", "NEEDS_REVIEW"})


@dataclass(frozen=True, slots=True)
class RowReconciliation:
    """One safe, serializable comparison result; never contains OCR text."""

    status: str
    workbook_path: PurePosixPath
    sheet_name: str
    row_number: int
    work_code: str | None
    pdf_path: PurePosixPath | None
    confidence: Decimal | None
    reason_codes: tuple[str, ...]
    quantity_comparison: str
    workbook_quantity: Decimal | None
    workbook_unit: str | None
    pdf_quantity: Decimal | None
    pdf_unit: str | None
    cost_comparison: str = "NOT_COMPARABLE"

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError("unsupported reconciliation status")


def normalize_work_code(value: str | None) -> str | None:
    """Normalise only casing/whitespace: punctuation remains part of exact code."""
    if not value:
        return None
    result = re.sub(r"\s+", "", value).casefold()
    return result or None


def drawing_codes_for_row(
    row: WorkbookRowFact, rows: tuple[WorkbookRowFact, ...]
) -> tuple[str, ...]:
    """Inherit drawing context from nearest preceding dotted-prefix parent only."""
    code = normalize_work_code(row.work_code)
    if code is None:
        return ()
    parent_candidates: list[tuple[int, int, str]] = []
    for earlier in rows:
        earlier_code = normalize_work_code(earlier.work_code)
        if (
            earlier.sheet_name != row.sheet_name
            or earlier.row_number >= row.row_number
            or not earlier_code
            or not earlier.drawing_code
            or not code.startswith(f"{earlier_code}.")
        ):
            continue
        parent_candidates.append((len(earlier_code), earlier.row_number, earlier.drawing_code))
    if not parent_candidates:
        return ()
    longest = max(length for length, _number, _drawing in parent_candidates)
    nearest = max(
        (item for item in parent_candidates if item[0] == longest), key=lambda item: item[1]
    )
    return (nearest[2],)


def reconcile_row(
    row: WorkbookRowFact,
    workbook_path: PurePosixPath,
    candidates: tuple[PdfDocumentEvidence, ...],
    *,
    drawing_codes: tuple[str, ...] = (),
) -> RowReconciliation:
    """Match only exact-scope candidates with an independent content signal."""
    base = _base(row, workbook_path)
    if not row.work_code:
        return _result(base, "NEEDS_REVIEW", ("missing_work_code",))
    if not candidates:
        return _result(base, "NO_EVIDENCE", ("no_exact_work_code_candidate",))
    usable = [candidate for candidate in candidates if candidate.document_type == "aosr"]
    if not usable:
        return _result(base, "NEEDS_REVIEW", ("unsupported_document_type",))
    scored = [(_signals(row, candidate, drawing_codes), candidate) for candidate in usable]
    supported = [(signals, candidate) for signals, candidate in scored if signals]
    if not supported:
        return _result(base, "NEEDS_REVIEW", ("independent_content_signal_missing",))
    supported.sort(key=lambda item: (len(item[0]), item[1].relative_path.as_posix()), reverse=True)
    top_count = len(supported[0][0])
    top = [(signals, candidate) for signals, candidate in supported if len(signals) == top_count]
    if len(top) > 1:
        return _result(base, "AMBIGUOUS", ("equally_strong_candidates",))
    signals, candidate = top[0]
    if candidate.text_source == "ocr" and (
        candidate.mean_ocr_confidence is None or candidate.mean_ocr_confidence < MIN_OCR_CONFIDENCE
    ):
        return _result(base, "NEEDS_REVIEW", (*signals, "low_ocr_confidence"), candidate)
    if candidate.text_source in {"error", "empty"}:
        return _result(base, "NEEDS_REVIEW", (*signals, "pdf_text_unavailable"), candidate)
    compared = _compare_quantity(row, candidate)
    status = "MISMATCH" if compared[0] == "MISMATCH" else "MATCH"
    return _result(
        base,
        status,
        signals,
        candidate,
        quantity_comparison=compared[0],
        pdf_quantity=compared[1],
        pdf_unit=compared[2],
    )


def _base(
    row: WorkbookRowFact, workbook_path: PurePosixPath
) -> tuple[PurePosixPath, str, int, str | None, Decimal | None, str | None]:
    return workbook_path, row.sheet_name, row.row_number, row.work_code, row.quantity, row.unit


def _result(
    base: tuple[PurePosixPath, str, int, str | None, Decimal | None, str | None],
    status: str,
    reasons: tuple[str, ...],
    candidate: PdfDocumentEvidence | None = None,
    quantity_comparison: str = "NOT_COMPARABLE",
    pdf_quantity: Decimal | None = None,
    pdf_unit: str | None = None,
) -> RowReconciliation:
    workbook_path, sheet_name, row_number, work_code, workbook_quantity, workbook_unit = base
    return RowReconciliation(
        status=status,
        workbook_path=workbook_path,
        sheet_name=sheet_name,
        row_number=row_number,
        work_code=work_code,
        pdf_path=candidate.relative_path if candidate else None,
        confidence=Decimal("1.0") if candidate and status in {"MATCH", "MISMATCH"} else None,
        reason_codes=tuple(dict.fromkeys(reasons)),
        quantity_comparison=quantity_comparison,
        workbook_quantity=workbook_quantity,
        workbook_unit=workbook_unit,
        pdf_quantity=pdf_quantity,
        pdf_unit=pdf_unit,
    )


def _signals(
    row: WorkbookRowFact, candidate: PdfDocumentEvidence, drawing_codes: tuple[str, ...]
) -> tuple[str, ...]:
    signals: list[str] = []
    backbone = {_normalise_code(code) for code in drawing_codes if _normalise_code(code)}
    if backbone & {_normalise_code(code) for code in candidate.project_codes}:
        signals.append("project_code_match")
    if _similar_work_names(row.work_name, candidate.work_description):
        signals.append("work_description_similarity")
    return tuple(signals)


def _normalise_code(value: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", value.casefold())


def _similar_work_names(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    stop = {"работ", "работы", "устройство", "выполнены", "следующие", "скрытых"}
    left_tokens = {
        token for token in re.findall(r"[a-zа-яё0-9]{3,}", left.casefold()) if token not in stop
    }
    right_tokens = {
        token for token in re.findall(r"[a-zа-яё0-9]{3,}", right.casefold()) if token not in stop
    }
    overlap = len(left_tokens & right_tokens)
    return bool(overlap) and overlap * 10 >= min(len(left_tokens), len(right_tokens)) * 6


def _compare_quantity(
    row: WorkbookRowFact, candidate: PdfDocumentEvidence
) -> tuple[str, Decimal | None, str | None]:
    if row.quantity is None or not row.unit:
        return "NOT_COMPARABLE", None, None
    if len(candidate.quantity_candidates) != 1 or len(candidate.unit_candidates) != 1:
        return "NOT_COMPARABLE", None, None
    try:
        pdf_quantity = Decimal(candidate.quantity_candidates[0])
    except Exception:
        return "NOT_COMPARABLE", None, None
    workbook_unit, pdf_unit = _unit(row.unit), _unit(candidate.unit_candidates[0])
    if workbook_unit is None or pdf_unit is None:
        return "NOT_COMPARABLE", pdf_quantity, candidate.unit_candidates[0]
    if {workbook_unit, pdf_unit} <= {"m", "km"}:
        left = row.quantity * (Decimal("1000") if workbook_unit == "km" else Decimal("1"))
        right = pdf_quantity * (Decimal("1000") if pdf_unit == "km" else Decimal("1"))
    elif workbook_unit == pdf_unit:
        left, right = row.quantity, pdf_quantity
    else:
        return "NOT_COMPARABLE", pdf_quantity, candidate.unit_candidates[0]
    return ("MATCH" if left == right else "MISMATCH"), pdf_quantity, candidate.unit_candidates[0]


def _unit(value: str) -> str | None:
    normalized = re.sub(r"\s+", "", value.casefold()).rstrip(".")
    return {
        "м": "m",
        "мп": "m",
        "км": "km",
        "м2": "m2",
        "м²": "m2",
        "м3": "m3",
        "шт": "pcs",
        "т": "t",
        "кг": "kg",
    }.get(normalized)
