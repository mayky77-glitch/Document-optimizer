from excel_to_tad.normalization import (
    infer_column_role,
    is_structural_empty,
    is_text_identifier_header,
    stringify_identifier_cell,
    to_float,
)


def test_numeric_columns_ignore_service_dots() -> None:
    assert infer_column_role("в отчетном периоде", [6.0, ".", 0.0]) == "float"
    assert infer_column_role("остаток", [8.0, ".", 0.8412]) == "float"


def test_mixed_column_stays_text() -> None:
    assert infer_column_role("с/п", ["ЛГСС", 0.0, "0.0"]) == "text"


def test_identifier_has_no_trailing_dot_zero() -> None:
    assert stringify_identifier_cell(1.0) == "1"
    assert stringify_identifier_cell("002.0") == "002"
    assert stringify_identifier_cell("1.2") == "1.2"
    assert stringify_identifier_cell("1.1.3") == "1.1.3"


def test_float_noise_cleanup_is_not_fixed_rounding() -> None:
    assert to_float(80.810000000001) == 80.81
    assert to_float(2288.0539) == 2288.0539
    assert to_float(1.42277) == 1.42277
    assert to_float(0.8412) == 0.8412


def test_structural_placeholders() -> None:
    assert is_structural_empty(".")
    assert is_structural_empty("-")
    assert not is_structural_empty("ЛГСС")


def test_no_pp_header_is_always_identifier_text() -> None:
    assert is_text_identifier_header("No п/п")
    assert infer_column_role("No п/п", [1.0, 2.0, 3.0]) == "text"
