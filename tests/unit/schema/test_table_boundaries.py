from report_processor.schema.table_boundaries import _looks_like_data, _looks_like_numbering_row


def test_numbering_rows_cover_numeric_strings_formulas_and_hide_markers():
    assert _looks_like_numbering_row(["1", "2", "3", "скрыть"])
    assert _looks_like_numbering_row(["=B23+1", "2", "3", "скрывается"])
    assert _looks_like_numbering_row([1, "2.3", 4, "5"])


def test_realistic_data_row_is_not_a_numbering_row():
    values = ["Монтаж трубопровода", "м", 12.5, 1000]
    assert not _looks_like_numbering_row(values)
    assert _looks_like_data(values)
