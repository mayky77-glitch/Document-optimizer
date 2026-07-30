from report_processor.drawing_card.models import ManifestEntry
from report_processor.drawing_card.sources.identity import resolve_object_identity
from report_processor.drawing_card.statuses import Status


def _entry(name: str) -> ManifestEntry:
    return ManifestEntry(
        file_id="id",
        source_kind="file",
        container_path="/tmp/" + name,
        logical_path=name,
        filename=name,
        extension=".xlsx",
        size=1,
        compressed_size=None,
        object_index_hint=None,
        document_type="visr",
        period=None,
        revision=None,
        is_temporary=False,
        is_copy=False,
        is_outdated=False,
        status="OK",
    )


def test_leading_zero_is_preserved() -> None:
    result = resolve_object_identity(_entry("0906 ВиСР.xlsx"))
    assert result.value == "0906"
    assert result.source == "filename"


def test_conflicting_sources_are_not_resolved_silently() -> None:
    result = resolve_object_identity(
        _entry("0906 ВиСР.xlsx"),
        mapping={"*": "0845"},
    )
    assert result.value is None
    assert result.status == Status.OBJECT_CONFLICT
    assert result.candidates == ("0845", "0906")
