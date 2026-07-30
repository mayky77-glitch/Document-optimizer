from report_processor.identifiers.document_index import extract_document_index
from report_processor.metadata.periods import DocumentPeriod
from report_processor.selection.models import SourceSelectionRequest
from report_processor.selection.selector import select_source_file


def test_selection_on_10000_prebuilt_entries(make_entry, make_manifest) -> None:
    target_index = extract_document_index("1006 (682)").value
    other_index = extract_document_index("0842 (623)").value
    entries = []
    for position in range(10_000):
        entry = make_entry(
            f"entry_{position}.xlsx",
            file_id=str(position),
            document_type="ks6a",
        )
        entry.document_index = target_index if position == 9_999 else other_index
        entry.document_index_status = "OK"
        entry.document_period = DocumentPeriod(2026, 7)
        entry.document_period_status = "OK"
        entries.append(entry)
    result = select_source_file(
        make_manifest(entries),
        SourceSelectionRequest(
            target_index=target_index,
            target_period=DocumentPeriod(2026, 7),
            preferred_document_types=("ks6a",),
            allowed_document_types=("ks6a",),
        ),
    )
    assert result.status == "OK"
    assert result.selected.file_id == "9999"
