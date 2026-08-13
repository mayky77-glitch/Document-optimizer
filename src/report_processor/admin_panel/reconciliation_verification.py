"""Private authoritative document-verification execution.

This module deliberately reuses the reconciliation review authority.  It does
not inspect local-RAG hints or expose workbook provenance outside the artifact
writer boundary.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from report_processor.excel_writer.ooxml import publish_no_clobber

from .reconciliation_execution import _review_row_id, prepare_review
from .reconciliation_numeric_verification import NumericVerificationFailure, verify_numeric

_MAX_RESULT_BYTES = 256 * 1024 * 1024
_PASSED_MESSAGE = "Все документы проверены. Ошибок не найдено."
_FAILED_MESSAGE = "Проверка завершена: обнаружены ошибки. Проблемные строки выделены красным."


class VerificationTechnicalFailure(RuntimeError):
    """A controlled unreadable or incomplete verification input."""

    def __init__(self, code: str, issues: tuple[object, ...] = ()) -> None:
        super().__init__(code)
        self.issues = issues


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Private verification facts projected by ``presentation`` without locations."""

    verification_status: str
    message: str
    checked_row_count: int
    failed_row_count: int
    output: Path | None = None
    result_name: str | None = None


def verify_reconciliation(job, feedback) -> VerificationResult:
    """Classify source rows with the existing reconciliation authority.

    A row passes only when the newest authoritative decision accepts it or its
    group is in a safe DecisionPackage.  Explicit rejection always wins.
    """

    review = prepare_review(job, feedback)
    if review.state is None or review.source_batch is None:
        issues = review.source_issues
        if review.target_error:
            issues = (
                {
                    "basename": getattr(job, "target_name", "report.xlsx"),
                    "comment": "Не удалось прочитать структуру целевого отчёта.",
                    "repair_hint": "Проверьте шаблон отчёта и повторите загрузку.",
                    "can_continue": False,
                },
            )
        raise VerificationTechnicalFailure("VERIFICATION_INPUT_UNUSABLE", issues)
    if review.source_batch.issues:
        raise VerificationTechnicalFailure(
            "VERIFICATION_INPUT_UNUSABLE", review.source_batch.issues
        )

    locations = _source_locations(job, review.source_batch.rows)
    try:
        failed_row_ids, checked = verify_numeric(job, review)
    except NumericVerificationFailure as error:
        raise VerificationTechnicalFailure(str(error)) from error

    failed_locations: dict[Path, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for row_id in sorted(failed_row_ids):
        location = locations.get(row_id)
        if location is None:
            raise VerificationTechnicalFailure("VERIFICATION_LOCATION_UNAVAILABLE")
        source, sheet_name, row_number = location
        failed_locations[source][sheet_name].add(row_number)

    if not failed_row_ids:
        return VerificationResult("passed", _PASSED_MESSAGE, checked, 0)
    output, result_name = _write_artifact(job, failed_locations)
    return VerificationResult(
        "failed", _FAILED_MESSAGE, checked, len(failed_row_ids), output, result_name
    )


def _source_locations(job, rows) -> dict[str, tuple[Path, str, int]]:
    sources = tuple(getattr(job, "sources", ()) or (job.source,))
    names = tuple(getattr(job, "source_names", ()) or ())
    if names and len(names) != len(sources):
        raise VerificationTechnicalFailure("VERIFICATION_SOURCE_MAPPING_UNAVAILABLE")
    names = names or tuple(path.name for path in sources)
    by_name = {name: path for name, path in zip(names, sources, strict=True)}
    if len(by_name) != len(sources):
        raise VerificationTechnicalFailure("VERIFICATION_SOURCE_MAPPING_UNAVAILABLE")
    values: dict[str, tuple[Path, str, int]] = {}
    for source_row in rows:
        review_row_id = _review_row_id(job, source_row.source_row_id)
        sheet_name = source_row.source_sheet
        row_number = source_row.source_row_number
        source = by_name.get(source_row.source_filename)
        if (
            source is None
            or not isinstance(sheet_name, str)
            or not sheet_name
            or not isinstance(row_number, int)
            or row_number < 1
        ):
            raise VerificationTechnicalFailure("VERIFICATION_LOCATION_UNAVAILABLE")
        values[review_row_id] = source, sheet_name, row_number
    return values


def _write_artifact(
    job,
    failed_locations: Mapping[Path, Mapping[str, Collection[int]]],
) -> tuple[Path, str]:
    sources = tuple(getattr(job, "sources", ()) or (job.source,))
    names = tuple(getattr(job, "source_names", ()) or ())
    names = names or tuple(path.name for path in sources)
    if len(sources) != len(names):
        raise VerificationTechnicalFailure("VERIFICATION_SOURCE_MAPPING_UNAVAILABLE")
    if len(sources) == 1:
        source, source_name = sources[0], names[0]
        result_name = f"Проверено_{Path(source_name).name}"
        output = job.directory / f"verification{source.suffix.casefold()}"
        _annotate(source, output, failed_locations.get(source, {}))
        return output, result_name

    output = job.directory / "verification-documents.zip"
    temporary_directory = Path(
        tempfile.mkdtemp(prefix=".verification-artifact-", dir=job.directory)
    )
    temporary_output = temporary_directory / output.name
    try:
        with zipfile.ZipFile(
            temporary_output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for index, (source, source_name) in enumerate(zip(sources, names, strict=True), 1):
                member = Path(source_name).name
                annotated = failed_locations.get(source)
                if annotated:
                    copied = temporary_directory / (
                        f"verification-source-{index:02d}{source.suffix.casefold()}"
                    )
                    _annotate(source, copied, annotated)
                    archive.write(copied, member)
                else:
                    archive.write(source, member)
        _verify_zip_artifact(temporary_output, tuple(Path(name).name for name in names))
        if temporary_output.stat().st_size > _MAX_RESULT_BYTES:
            raise VerificationTechnicalFailure("VERIFICATION_RESULT_TOO_LARGE")
        os.chmod(temporary_output, 0o600)
        publish_no_clobber(temporary_output, output)
        return output, "Проверка_документов.zip"
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


def _verify_zip_artifact(path: Path, expected_names: tuple[str, ...]) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            if tuple(archive.namelist()) != expected_names or archive.testzip() is not None:
                raise VerificationTechnicalFailure("VERIFICATION_ARTIFACT_INVALID")
    except VerificationTechnicalFailure:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise VerificationTechnicalFailure("VERIFICATION_ARTIFACT_INVALID") from error


def _annotate(source: Path, output: Path, rows: Mapping[str, Collection[int]]) -> None:
    if not rows:
        raise VerificationTechnicalFailure("VERIFICATION_LOCATION_UNAVAILABLE")
    from report_processor.excel_writer.row_annotations import annotate_failed_rows

    annotated = annotate_failed_rows(source, output, rows)
    if annotated != output or not output.is_file() or output.is_symlink():
        raise VerificationTechnicalFailure("VERIFICATION_ANNOTATION_FAILED")
    os.chmod(output, 0o600)
