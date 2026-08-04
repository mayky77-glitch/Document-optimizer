"""Controlled classification and field extraction for construction-package PDFs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .ocr import (
    CommandRunner,
    OcrResult,
    extract_pdf_text_layer,
    ocr_pdf_pages,
    pdf_page_count,
    run_local_command,
)

MIN_OCR_CONFIDENCE = 70.0


@dataclass(frozen=True, slots=True)
class PdfDocumentEvidence:
    relative_path: PurePosixPath
    document_type: str
    page_count: int | None
    text_source: str
    act_number: str | None
    act_date: str | None
    project_codes: tuple[str, ...]
    work_description: str | None
    quantity_candidates: tuple[str, ...]
    unit_candidates: tuple[str, ...]
    mean_ocr_confidence: float | None
    issues: tuple[PdfEvidenceIssue, ...]


@dataclass(frozen=True, slots=True)
class PdfEvidenceIssue:
    code: str
    severity: str


def classify_document_name(filename: str) -> str:
    """Classify a basename conservatively; it never supplies a match key."""
    normalised = _normalise(filename)
    if any(marker in normalised for marker in ("аоср", "aocp", "aosr")):
        return "aosr"
    if any(marker in normalised for marker in ("ожр", "ojr", "ozhr")):
        return "ozhr"
    if "акт" in normalised or "act" in normalised:
        return "act"
    return "other"


def extract_pdf_evidence(pdf_path: Path, relative_path: PurePosixPath) -> PdfDocumentEvidence:
    """Extract only explicit fields from the first two pages of one PDF."""
    return analyse_pdf_document(pdf_path, relative_path)


def analyse_pdf_document(
    pdf_path: Path,
    relative_path: PurePosixPath,
    *,
    runner: CommandRunner = run_local_command,
) -> PdfDocumentEvidence:
    """Extract bounded evidence, carrying controlled failures for manual review."""
    document_type = classify_document_name(pdf_path.name)
    if not _is_safe_relative_path(relative_path):
        return _invalid_path_evidence(relative_path, document_type)
    page_count, page_count_error = pdf_page_count(pdf_path, runner=runner)
    result = extract_pdf_text_layer(pdf_path, runner=runner)
    if result.status in {"empty", "error"}:
        result = ocr_pdf_pages(pdf_path, runner=runner)
    issues = _issues(result.error_code, page_count_error, document_type, result)
    if result.status in {"error", "empty"}:
        return PdfDocumentEvidence(
            relative_path=relative_path,
            document_type=document_type,
            page_count=page_count,
            text_source=result.status,
            act_number=None,
            act_date=None,
            project_codes=(),
            work_description=None,
            quantity_candidates=(),
            unit_candidates=(),
            mean_ocr_confidence=result.mean_confidence,
            issues=issues,
        )
    fields = (
        extract_aosr_fields(result.text, basename=pdf_path.name)
        if document_type == "aosr"
        else _empty_fields()
    )
    return PdfDocumentEvidence(
        relative_path=relative_path,
        document_type=document_type,
        page_count=page_count,
        text_source=result.status,
        act_number=fields.act_number,
        act_date=fields.act_date,
        project_codes=fields.project_codes,
        work_description=fields.work_description,
        quantity_candidates=fields.quantity_candidates,
        unit_candidates=fields.unit_candidates,
        mean_ocr_confidence=result.mean_confidence,
        issues=issues,
    )


@dataclass(frozen=True, slots=True)
class AosrFields:
    act_number: str | None
    act_date: str | None
    project_codes: tuple[str, ...]
    work_description: str | None
    quantity_candidates: tuple[str, ...]
    unit_candidates: tuple[str, ...]


def extract_aosr_fields(text: str, *, basename: str | None = None) -> AosrFields:
    """Find explicit AОСР values without inventing a value from adjacent text."""
    compact = _normalise_whitespace(text)
    act_header = re.search(
        r"\bакт\s+освидетельствования\s+(?:скрытых\s+)?работ\s*№\s*([\w./-]{1,48})"
        r"(?P<nearby>.{0,180})",
        compact,
        re.IGNORECASE,
    )
    act_number = act_header.group(1).strip() if act_header else None
    act_date = _adjacent_act_date(act_header.group("nearby")) if act_header else None
    if act_date is None and basename:
        act_date = _basename_date(basename)
    project_codes = _project_codes(_sections_one_to_two(compact), excluded=(act_number,))
    work_description = _work_description(compact)
    quantities, quantity_units = _quantity_candidates(compact)
    units = tuple(
        dict.fromkeys(
            (
                *quantity_units,
                *(
                    unit.casefold()
                    for unit in re.findall(
                        r"\b(м3|м²|м2|м\.п\.|м|шт\.|шт|т|кг)\b", compact, re.IGNORECASE
                    )
                ),
            )
        )
    )[:12]
    return AosrFields(act_number, act_date, project_codes, work_description, quantities, units)


def _empty_fields() -> AosrFields:
    return AosrFields(None, None, (), None, (), ())


def _invalid_path_evidence(relative_path: PurePosixPath, document_type: str) -> PdfDocumentEvidence:
    return PdfDocumentEvidence(
        relative_path=relative_path,
        document_type=document_type,
        page_count=None,
        text_source="error",
        act_number=None,
        act_date=None,
        project_codes=(),
        work_description=None,
        quantity_candidates=(),
        unit_candidates=(),
        mean_ocr_confidence=None,
        issues=(PdfEvidenceIssue("unsafe_relative_path", "error"),),
    )


def _issues(
    extraction_error: str | None,
    page_count_error: str | None,
    document_type: str,
    result: OcrResult,
) -> tuple[PdfEvidenceIssue, ...]:
    issues: list[PdfEvidenceIssue] = []
    if page_count_error:
        issues.append(PdfEvidenceIssue(page_count_error, "warning"))
    if extraction_error:
        issues.append(PdfEvidenceIssue(extraction_error, "error"))
    if result.status == "ocr" and (
        result.mean_confidence is None or result.mean_confidence < MIN_OCR_CONFIDENCE
    ):
        issues.append(PdfEvidenceIssue("low_ocr_confidence", "warning"))
    if document_type != "aosr":
        issues.append(PdfEvidenceIssue("unsupported_document_type", "info"))
    return tuple(issues)


def _is_safe_relative_path(value: PurePosixPath) -> bool:
    return not value.is_absolute() and ".." not in value.parts and value.parts not in {(), (".",)}


def _adjacent_act_date(value: str) -> str | None:
    match = re.search(
        r"\b(?:от|дата)\s*("
        r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
        r"|[«\"]?\d{1,2}[»\"]?\s+"
        r"(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}"
        r")",
        value,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _basename_date(value: str) -> str | None:
    match = re.search(r"\bот\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b", value, re.IGNORECASE)
    return match.group(1) if match else None


def _work_description(value: str) -> str | None:
    match = re.search(
        r"к\s+освидетельствованию\s+предъявлены\s+следующие\s+работы\s*[:—-]?\s*"
        r"(.{3,1200}?)(?=\b2\s*[.)]|$)",
        value,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" .;:")
    match = re.search(
        r"(?:наименование|вид)\s+(?:работ|скрытых\s+работ)\s*[:—-]?\s*"
        r"(.{3,500}?)(?=\s{2,}|\b(?:объект|проект|количеств|единиц)\b|$)",
        value,
        re.IGNORECASE,
    )
    return match.group(1).strip(" .;:") if match else None


def _quantity_candidates(value: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pairs = re.findall(
        r"\b(?:[LSV]\s*=\s*|(?:количество|объем|объём)\s*[:=—-]?\s*)"
        r"(\d+(?:[., ]\d+)?)\s*(м3|м²|м2|м\.п\.|м|шт\.|шт|т|кг)\b",
        value,
        re.IGNORECASE,
    )
    return (
        tuple(dict.fromkeys(quantity.replace(" ", "") for quantity, _unit in pairs))[:12],
        tuple(dict.fromkeys(unit.casefold() for _quantity, unit in pairs))[:12],
    )


def _sections_one_to_two(value: str) -> str:
    return re.split(r"\b3\s*[.)]", value, maxsplit=1)[0]


def _project_codes(value: str, *, excluded: tuple[str | None, ...] = ()) -> tuple[str, ...]:
    candidates = re.findall(
        r"(?<!\w)[A-ZА-ЯЁ0-9]{1,16}(?:[./-][A-ZА-ЯЁ0-9]{1,16})+(?!\w)", value, re.IGNORECASE
    )
    accepted: list[str] = []
    excluded_codes = {item.upper() for item in excluded if item}
    for candidate in candidates:
        code = candidate.upper()
        if code in excluded_codes:
            continue
        if len(code) < 5 or re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", code):
            continue
        if not ("/" in code or re.search(r"[A-ZА-ЯЁ]", code) or code.count(".") >= 2):
            continue
        accepted.append(code)
    return tuple(dict.fromkeys(accepted))[:12]


def _normalise(value: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", value.casefold())


def _normalise_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
