"""Bounded, local-only OCR helpers for package reconciliation.

The module deliberately keeps transient images and OCR output in a temporary
directory.  Callers receive structured evidence only; they decide whether any
of it belongs in an explicitly requested report.
"""

from __future__ import annotations

import csv
import re
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 45
OCR_DPI = 300
OCR_LANGUAGES = "rus+eng"


@dataclass(frozen=True, slots=True)
class OcrToken:
    text: str
    confidence: float
    page: int
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class OcrResult:
    status: str
    text: str
    mean_confidence: float | None
    tokens: tuple[OcrToken, ...]
    error_code: str | None = None


CommandRunner = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]


def run_local_command(
    args: Sequence[str], timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    """Run one fixed local command without a shell or inherited stdin."""
    return subprocess.run(
        list(args),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        timeout=timeout_seconds,
    )


def extract_pdf_text_layer(
    pdf_path: Path,
    *,
    first_page: int = 1,
    last_page: int = 2,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    runner: CommandRunner = run_local_command,
) -> OcrResult:
    """Read a PDF text layer, returning a controlled status on tool failures."""
    if not _valid_pdf_request(pdf_path, first_page, last_page):
        return OcrResult("error", "", None, (), "invalid_pdf_request")
    try:
        completed = runner(
            ("pdftotext", "-f", str(first_page), "-l", str(last_page), str(pdf_path), "-"),
            timeout_seconds,
        )
    except FileNotFoundError:
        return OcrResult("error", "", None, (), "pdftotext_unavailable")
    except subprocess.TimeoutExpired:
        return OcrResult("error", "", None, (), "pdftotext_timeout")
    except OSError:
        return OcrResult("error", "", None, (), "pdftotext_failed")
    if completed.returncode != 0:
        return OcrResult("error", "", None, (), "pdftotext_failed")
    text = _normalise_text(completed.stdout)
    return OcrResult("text_layer" if text else "empty", text, None, ())


def pdf_page_count(
    pdf_path: Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    runner: CommandRunner = run_local_command,
) -> tuple[int | None, str | None]:
    """Read the page count through pdfinfo without accepting arbitrary output."""
    if not _valid_pdf_request(pdf_path, 1, 1):
        return None, "invalid_pdf_request"
    try:
        completed = runner(("pdfinfo", str(pdf_path)), timeout_seconds)
    except FileNotFoundError:
        return None, "pdfinfo_unavailable"
    except subprocess.TimeoutExpired:
        return None, "pdfinfo_timeout"
    except OSError:
        return None, "pdfinfo_failed"
    if completed.returncode != 0:
        return None, "pdfinfo_failed"
    match = re.search(r"^Pages:\s*(\d+)\s*$", completed.stdout, re.MULTILINE)
    if not match or int(match.group(1)) < 1:
        return None, "pdfinfo_invalid_output"
    return int(match.group(1)), None


def ocr_pdf_pages(
    pdf_path: Path,
    *,
    first_page: int = 1,
    last_page: int = 2,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    runner: CommandRunner = run_local_command,
) -> OcrResult:
    """Render selected PDF pages locally and OCR their TSV output.

    No page image or raw TSV is retained when this function returns.
    """
    if not _valid_pdf_request(pdf_path, first_page, last_page):
        return OcrResult("error", "", None, (), "invalid_pdf_request")
    with tempfile.TemporaryDirectory(prefix="package-reconciliation-ocr-") as temporary_dir:
        output_prefix = Path(temporary_dir) / "page"
        try:
            render = runner(
                (
                    "pdftoppm",
                    "-png",
                    "-r",
                    str(OCR_DPI),
                    "-f",
                    str(first_page),
                    "-l",
                    str(last_page),
                    str(pdf_path),
                    str(output_prefix),
                ),
                timeout_seconds,
            )
        except FileNotFoundError:
            return OcrResult("error", "", None, (), "pdftoppm_unavailable")
        except subprocess.TimeoutExpired:
            return OcrResult("error", "", None, (), "pdftoppm_timeout")
        except OSError:
            return OcrResult("error", "", None, (), "pdftoppm_failed")
        if render.returncode != 0:
            return OcrResult("error", "", None, (), "pdftoppm_failed")

        page_files = sorted(Path(temporary_dir).glob("page-*.png"))
        if not page_files:
            return OcrResult("error", "", None, (), "rendered_pages_missing")
        all_tokens: list[OcrToken] = []
        for page_index, image_path in enumerate(page_files, start=first_page):
            parsed = _ocr_image_tsv(image_path, page_index, timeout_seconds, runner)
            if parsed.error_code:
                return parsed
            all_tokens.extend(parsed.tokens)
    text = _tokens_to_text(all_tokens)
    confidence_values = [token.confidence for token in all_tokens if token.confidence >= 0]
    mean_confidence = (
        round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else None
    )
    return OcrResult("ocr" if text else "empty", text, mean_confidence, tuple(all_tokens))


def _ocr_image_tsv(
    image_path: Path,
    page_number: int,
    timeout_seconds: float,
    runner: CommandRunner,
) -> OcrResult:
    try:
        completed = runner(
            ("tesseract", str(image_path), "stdout", "-l", OCR_LANGUAGES, "--psm", "6", "tsv"),
            timeout_seconds,
        )
    except FileNotFoundError:
        return OcrResult("error", "", None, (), "tesseract_unavailable")
    except subprocess.TimeoutExpired:
        return OcrResult("error", "", None, (), "tesseract_timeout")
    except OSError:
        return OcrResult("error", "", None, (), "tesseract_failed")
    if completed.returncode != 0:
        return OcrResult("error", "", None, (), "tesseract_failed")
    return OcrResult("ocr", "", None, tuple(parse_tesseract_tsv(completed.stdout, page_number)))


def parse_tesseract_tsv(tsv: str, page_number: int) -> list[OcrToken]:
    """Parse only word-level TSV rows with useful text and coordinates."""
    tokens: list[OcrToken] = []
    for row in csv.DictReader(tsv.splitlines(), delimiter="\t"):
        value = (row.get("text") or "").strip()
        if not value or row.get("level") != "5":
            continue
        try:
            confidence = float(row["conf"])
            left = int(row["left"])
            top = int(row["top"])
            width = int(row["width"])
            height = int(row["height"])
        except (KeyError, TypeError, ValueError):
            continue
        tokens.append(OcrToken(value, confidence, page_number, left, top, width, height))
    return tokens


def _valid_pdf_request(pdf_path: Path, first_page: int, last_page: int) -> bool:
    return (
        pdf_path.is_file()
        and not pdf_path.is_symlink()
        and pdf_path.suffix.casefold() == ".pdf"
        and 1 <= first_page <= last_page <= 2
    )


def _tokens_to_text(tokens: Sequence[OcrToken]) -> str:
    return _normalise_text(" ".join(token.text for token in tokens))


def _normalise_text(value: str) -> str:
    return "\n".join(
        line.strip() for line in value.replace("\x00", "").splitlines() if line.strip()
    )
