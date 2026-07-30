from report_processor.drawing_card.models import ManifestEntry, SourceSchema
from report_processor.drawing_card.sources.extractor import extract_rows
from report_processor.drawing_card.statuses import Status


class _Reader:
    def __init__(self, rows):
        self.rows = rows

    def iter_rows(self, _sheet_name, **_kwargs):
        yield from self.rows

    def list_sheets(self):
        return ("КС-6а",)

    def close(self):
        return None


def _row(*values):
    return tuple(values)


def _entry() -> ManifestEntry:
    return ManifestEntry(
        file_id="file-1",
        source_kind="file",
        container_path="/tmp/source.xlsx",
        logical_path="source.xlsx",
        filename="source.xlsx",
        extension=".xlsx",
        size=1,
        compressed_size=1,
        object_index_hint="0906",
        document_type="ks6a",
        period="2026-07",
        revision=None,
        is_temporary=False,
        is_copy=False,
        is_outdated=False,
        status=Status.OK.value,
    )


def _schema() -> SourceSchema:
    return SourceSchema(
        sheet_name="КС-6а",
        header_start_row=1,
        header_end_row=2,
        data_start_row=3,
        columns={
            "drawing_code": 1,
            "work_name": 2,
            "unit": 3,
            "remaining_quantity": 4,
            "remaining_total_cost": 5,
        },
        logical_headers={},
        confidence=1.0,
        status=Status.OK.value,
    )


def test_unit_marker_does_not_replace_parent_drawing_code() -> None:
    parent = "0092.049.Р.13/1.0004.УКПГ.045.0724.006-ТХ"
    rows = [
        (_row(parent, None, None, None, None), _row(parent, None, None, None, None)),
        (
            _row("м", "Монтаж ТТ Д 57-89", "м", 12, 5000),
            _row("м", "Монтаж ТТ Д 57-89", "м", 12, 5000),
        ),
        (_row(None, "Монтаж ЗРА", "шт", 2, 3000), _row(None, "Монтаж ЗРА", "шт", 2, 3000)),
    ]
    extracted = list(extract_rows(_Reader(rows), _entry(), _schema(), "0906"))
    assert [item.drawing_code_raw for item in extracted] == [parent, parent]
    assert "IGNORED_NON_DRAWING_CELL:м" in extracted[0].warnings


def test_real_code_on_detail_row_can_start_new_group() -> None:
    rows = [
        (
            _row("КЖ-001", "Бетонирование", "м3", 4, 100),
            _row("КЖ-001", "Бетонирование", "м3", 4, 100),
        ),
        (
            _row("КЖ-002", "Бетонирование", "м3", 5, 200),
            _row("КЖ-002", "Бетонирование", "м3", 5, 200),
        ),
    ]
    extracted = list(extract_rows(_Reader(rows), _entry(), _schema(), "0906"))
    assert [item.drawing_code_raw for item in extracted] == ["КЖ-001", "КЖ-002"]
