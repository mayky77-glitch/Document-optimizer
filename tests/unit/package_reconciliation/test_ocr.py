from __future__ import annotations

import subprocess
from pathlib import Path

from report_processor.package_reconciliation.ocr import (
    OcrResult,
    OcrToken,
    extract_pdf_text_layer,
    ocr_pdf_pages,
    parse_tesseract_tsv,
    pdf_page_count,
)


def _pdf(tmp_path: Path) -> Path:
    path = tmp_path / "source.pdf"
    path.write_text("not a binary fixture")
    return path


def test_extracts_usable_text_layer_with_bounded_arguments(tmp_path: Path) -> None:
    calls: list[tuple[tuple[str, ...], float]] = []

    def runner(args: tuple[str, ...], timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append((args, timeout))
        return subprocess.CompletedProcess(args, 0, " АОСР № 7 \n Работы ", "")

    result = extract_pdf_text_layer(_pdf(tmp_path), runner=runner)

    assert result == OcrResult("text_layer", "АОСР № 7\nРаботы", None, ())
    assert calls == [(("pdftotext", "-f", "1", "-l", "2", str(_pdf(tmp_path)), "-"), 45)]


def test_text_layer_controls_missing_tool_and_timeout(tmp_path: Path) -> None:
    def missing(*_args: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    def timeout(*_args: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("pdftotext", 45)

    assert (
        extract_pdf_text_layer(_pdf(tmp_path), runner=missing).error_code == "pdftotext_unavailable"
    )
    assert extract_pdf_text_layer(_pdf(tmp_path), runner=timeout).error_code == "pdftotext_timeout"


def test_parse_tesseract_tsv_keeps_word_coordinates_only() -> None:
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t10\t20\t30\t40\t92.5\tРабота\n"
        "4\t1\t1\t1\t1\t0\t0\t0\t0\t0\t-1\t\n"
        "5\t1\t1\t1\t1\t2\t40\t20\t12\t40\tbad\t7"
    )

    assert parse_tesseract_tsv(tsv, 2) == [OcrToken("Работа", 92.5, 2, 10, 20, 30, 40)]


def test_ocr_renders_then_uses_tsv_and_never_keeps_temp_files(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path)

    def runner(args: tuple[str, ...], _timeout: float) -> subprocess.CompletedProcess[str]:
        if args[0] == "pdftoppm":
            Path(f"{args[-1]}-1.png").write_text("rendered")
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(
            args,
            0,
            "level\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t2\t3\t4\t88\tТекст\n",
            "",
        )

    result = ocr_pdf_pages(pdf, runner=runner)

    assert result.status == "ocr"
    assert result.text == "Текст"
    assert result.mean_confidence == 88.0
    assert result.tokens[0].page == 1


def test_rejects_symlink_and_invalid_page_range(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path)
    assert extract_pdf_text_layer(pdf, first_page=0).error_code == "invalid_pdf_request"
    linked = tmp_path / "linked.pdf"
    linked.symlink_to(pdf)
    assert ocr_pdf_pages(linked).error_code == "invalid_pdf_request"


def test_reads_page_count_with_controlled_invalid_output(tmp_path: Path) -> None:
    def runner(args: tuple[str, ...], _timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "Pages: 4\n", "")

    assert pdf_page_count(_pdf(tmp_path), runner=runner) == (4, None)

    def invalid(args: tuple[str, ...], _timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "Pages: zero\n", "")

    assert pdf_page_count(_pdf(tmp_path), runner=invalid) == (None, "pdfinfo_invalid_output")
