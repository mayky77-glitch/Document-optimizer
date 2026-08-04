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
    fields = extract_aosr_fields(result.text) if document_type == "aosr" else _empty_fields()
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


def extract_aosr_fields(text: str) -> AosrFields:
    """Find explicit AОСР values without inventing a value from adjacent text."""
    compact = _normalise_whitespace(text)
    act_number = _first_group(
        r"(?:акт(?:а)?\s*(?:освидетельствования)?\s*(?:скрытых)?\s*работ)?\s*№\s*([\w./-]{1,48})",
        compact,
    )
    act_date = _first_group(r"(?:от|дата)\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", compact)
    project_codes = tuple(
        dict.fromkeys(
            match.upper()
            for match in re.findall(
                r"\b(?:[A-ZА-ЯЁ]{1,6}[-/]?\d[\w./-]{2,})\b", compact, re.IGNORECASE
            )
        )
    )[:12]
    work_description = _section_value(
        compact,
        r"(?:наименование|вид)\s+(?:работ|скрытых\s+работ)\s*[:—-]?\s*",
    )
    quantities = tuple(
        dict.fromkeys(re.findall(r"\b\d+(?:[ .,]\d+)?\b", _after_quantity_label(compact)))
    )[:12]
    units = tuple(
        dict.fromkeys(
            unit.casefold()
            for unit in re.findall(r"\b(м3|м²|м2|м\.п\.|м|шт\.|шт|т|кг)\b", compact, re.IGNORECASE)
        )
    )[:12]
    return AosrFields(act_number, act_date, project_codes, work_description, quantities, units)


def _empty_fields() -> AosrFields:
    return AosrFields(None, None, (), None, (), ())


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


def _first_group(pattern: str, value: str) -> str | None:
    match = re.search(pattern, value, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _section_value(value: str, label_pattern: str) -> str | None:
    match = re.search(
        label_pattern + r"(.{3,500}?)(?=\s{2,}|\b(?:объект|проект|количеств|единиц)\b|$)",
        value,
        re.IGNORECASE,
    )
    return match.group(1).strip(" .;:") if match else None


def _after_quantity_label(value: str) -> str:
    match = re.search(r"(?:количество|объем|объём)\s*[:—-]?\s*([^\n]{0,200})", value, re.IGNORECASE)
    return match.group(1) if match else ""


def _normalise(value: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", value.casefold())


def _normalise_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
