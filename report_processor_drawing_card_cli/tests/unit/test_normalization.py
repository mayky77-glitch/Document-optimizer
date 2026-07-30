from decimal import Decimal

from report_processor.drawing_card.sources.normalization import (
    build_drawing_code,
    extract_object_candidates,
    normalize_unit,
    parse_decimal,
)


def test_decimal_preserves_zero_and_none() -> None:
    assert parse_decimal(0)[0] == Decimal("0")
    assert parse_decimal(None)[0] is None
    assert parse_decimal("1 234,50")[0] == Decimal("1234.50")


def test_drawing_group_is_preserved() -> None:
    drawing = build_drawing_code("ABC-1; ABC-2")
    assert drawing.raw == "ABC-1; ABC-2"
    assert drawing.components == ("ABC-1", "ABC-2")
    assert "DRAWING_CODE_GROUP_PRESERVED" in drawing.warnings


def test_object_and_unit_normalization() -> None:
    assert extract_object_candidates("объект 0906 / папка") == ("0906",)
    assert normalize_unit("м³") == "м3"
    assert normalize_unit("шт.") == "шт"


def test_binary_float_artifacts_are_normalized_without_rounding_real_precision() -> None:
    from report_processor.drawing_card.sources.normalization import parse_decimal

    value, warnings = parse_decimal("184178.2699999998")
    assert value == Decimal("184178.27")
    assert warnings and warnings[0].startswith("BINARY_FLOAT_ARTIFACT_NORMALIZED")

    small, small_warnings = parse_decimal("0.409999999916181")
    assert small == Decimal("0.41")
    assert small_warnings

    precise, precise_warnings = parse_decimal("1.23456789")
    assert precise == Decimal("1.23456789")
    assert precise_warnings == ()

    observed_artifacts = {
        "83108.99000000001": Decimal("83108.99"),
        "0.3999999985098839": Decimal("0.4"),
        "79969.21000000001": Decimal("79969.21"),
        "0.8097800000000001": Decimal("0.80978"),
        "8.859999999999999": Decimal("8.86"),
        "0.08999999985098839": Decimal("0.09"),
        "7837424.909999996": Decimal("7837424.91"),
        "8096917.769999996": Decimal("8096917.77"),
    }
    for raw, expected in observed_artifacts.items():
        normalized, artifact_warnings = parse_decimal(raw)
        assert normalized == expected
        assert artifact_warnings

    large_precise, large_warnings = parse_decimal("1000000000000.001")
    assert large_precise == Decimal("1000000000000.001")
    assert large_warnings == ()
