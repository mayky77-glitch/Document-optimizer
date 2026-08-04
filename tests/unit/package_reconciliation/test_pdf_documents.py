from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

from report_processor.package_reconciliation.pdf_documents import (
    AosrFields,
    analyse_pdf_document,
    classify_document_name,
    extract_aosr_fields,
)


def test_classifies_only_document_type_from_basename() -> None:
    assert classify_document_name("АОСР_сварка.pdf") == "aosr"
    assert classify_document_name("OZHR 12.PDF") == "ozhr"
    assert classify_document_name("Акт приемки.pdf") == "act"
    assert classify_document_name("photo-01.pdf") == "other"


def test_extracts_explicit_aosr_fields_from_text_fixture() -> None:
    evidence = extract_aosr_fields(
        "Акт освидетельствования скрытых работ № А-17 от 03.02.2026. "
        "Наименование работ: Устройство бетонной подготовки. "
        "Проект АБ-123/4. Объем: 12,5 м3."
    )

    assert evidence == AosrFields(
        act_number="А-17",
        act_date="03.02.2026",
        project_codes=("АБ-123/4",),
        work_description="Устройство бетонной подготовки",
        quantity_candidates=("12,5",),
        unit_candidates=("м3",),
    )


def test_does_not_invent_aosr_fields_when_text_has_no_labels() -> None:
    evidence = extract_aosr_fields("Произвольная строка 12 м3 без структурных полей")

    assert evidence.act_number is None
    assert evidence.act_date is None
    assert evidence.work_description is None
    assert evidence.quantity_candidates == ()
    assert evidence.unit_candidates == ("м3",)


def test_pdf_evidence_uses_text_layer_before_ocr_and_has_relative_path(tmp_path: Path) -> None:
    pdf = tmp_path / "АОСР-17.pdf"
    pdf.write_text("fixture only")

    def runner(args: tuple[str, ...], _timeout: float) -> subprocess.CompletedProcess[str]:
        if args[0] == "pdfinfo":
            return subprocess.CompletedProcess(args, 0, "Pages: 3\n", "")
        if args[0] == "pdftotext":
            return subprocess.CompletedProcess(
                args,
                0,
                "Акт освидетельствования скрытых работ № А-17 от 03.02.2026\n"
                "Наименование работ: Бетонная подготовка\nОбъем: 12,5 м3",
                "",
            )
        raise AssertionError(f"unexpected command: {args[0]}")

    evidence = analyse_pdf_document(pdf, PurePosixPath("0600/АОСР-17.pdf"), runner=runner)

    assert evidence.relative_path == PurePosixPath("0600/АОСР-17.pdf")
    assert evidence.page_count == 3
    assert evidence.text_source == "text_layer"
    assert evidence.act_number == "А-17"
    assert evidence.quantity_candidates == ("12,5",)
    assert not evidence.issues


def test_pdf_evidence_marks_low_confidence_ocr_for_manual_review(tmp_path: Path) -> None:
    pdf = tmp_path / "АОСР-17.pdf"
    pdf.write_text("fixture only")

    def runner(args: tuple[str, ...], _timeout: float) -> subprocess.CompletedProcess[str]:
        if args[0] == "pdfinfo":
            return subprocess.CompletedProcess(args, 0, "Pages: 1\n", "")
        if args[0] == "pdftotext":
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "pdftoppm":
            Path(f"{args[-1]}-1.png").write_text("rendered")
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(
            args,
            0,
            "level\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t2\t3\t4\t69\tТекст\n",
            "",
        )

    evidence = analyse_pdf_document(pdf, PurePosixPath("АОСР-17.pdf"), runner=runner)

    assert evidence.text_source == "ocr"
    assert evidence.mean_ocr_confidence == 69.0
    assert "low_ocr_confidence" in {issue.code for issue in evidence.issues}
