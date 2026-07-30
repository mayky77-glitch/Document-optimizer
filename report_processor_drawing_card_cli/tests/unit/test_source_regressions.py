from pathlib import Path
from zipfile import ZipFile

from report_processor.drawing_card.models import ManifestEntry, ObjectIdentityResult, SourceSchema
from report_processor.drawing_card.sources.identity import resolve_object_identity
from report_processor.drawing_card.sources.inspection import SourceInspection, select_inspections
from report_processor.drawing_card.sources.manifest import scan_archive
from report_processor.drawing_card.statuses import Status


def _entry(name: str, *, period: str | None = None, score_copy: bool = False) -> ManifestEntry:
    return ManifestEntry(
        file_id=name,
        source_kind="zip",
        container_path="/tmp/source.zip",
        logical_path=name,
        filename=name,
        extension=Path(name).suffix.lower(),
        size=1,
        compressed_size=1,
        object_index_hint=None,
        document_type="ks6a",
        period=period,
        revision=None,
        is_temporary=False,
        is_copy=score_copy,
        is_outdated=False,
        status=Status.OK.value,
    )


def _inspection(name: str, period: str, score: float) -> SourceInspection:
    entry = _entry(name, period=period)
    identity = ObjectIdentityResult("0907", "filename", 0.8, ("0907",), Status.OK, ())
    schema = SourceSchema(
        sheet_name="КС-6 ш 0907",
        header_start_row=12,
        header_end_row=14,
        data_start_row=15,
        columns={
            "drawing_code": 7,
            "work_name": 9,
            "unit": 10,
            "remaining_quantity": 171,
            "remaining_total_cost": 172,
        },
        logical_headers={},
        confidence=1.0,
        status=Status.OK,
    )
    return SourceInspection(
        entry, identity, (schema.sheet_name,), (schema,), (schema,), score, Status.OK, ()
    )


def test_filename_context_selects_real_object_and_ignores_year() -> None:
    result = resolve_object_identity(_entry("31_0109_22_Эт_13.1_07_2026_0907 (841)_КС-6.xlsx"))
    assert result.value == "0907"
    assert result.candidates == ("0907",)


def test_year_does_not_conflict_with_object_index() -> None:
    assert resolve_object_identity(_entry("# 0906 КС-6а июль 31_2026.xlsb")).value == "0906"
    assert resolve_object_identity(_entry("0908 КС-3_КС6а июль 2026.XLSX")).value == "0908"


def test_parenthesized_business_index_is_not_marked_as_copy(tmp_path: Path) -> None:
    archive_path = tmp_path / "sources.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("31_0109_22_Эт_13.1_07_2026_0907 (841)_КС-6.xlsx", b"x")
        archive.writestr("0907 КС-6 (1).xlsx", b"x")
    entries = scan_archive(archive_path)
    first = next(item for item in entries if "(841)" in item.filename)
    copy = next(item for item in entries if "(1)" in item.filename)
    assert first.object_index_hint == "0907"
    assert not first.is_copy
    assert copy.is_copy


def test_latest_period_is_selected_when_period_is_omitted() -> None:
    june = _inspection("0907_june.xlsx", "2026-06", 125.0)
    july = _inspection("0907_july.xlsx", "2026-07", 125.0)
    selected, records, warnings = select_inspections(
        [june, july], explicit_inputs=False, requested_period=None
    )
    assert [item.entry.filename for item in selected] == ["0907_july.xlsx"]
    assert not warnings
    assert any(
        record["logical_path"] == "0907_june.xlsx"
        and record["decision"] == "not_selected_older_period"
        for record in records
    )
