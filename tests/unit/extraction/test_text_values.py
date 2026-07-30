from report_processor.extraction import parse_text_value


def test_minimal_text_cleanup_preserves_meaning_and_punctuation():
    result = parse_text_value("  Работа\u00a0по\nмонтажу, этап № 1  ")
    assert result.value == "Работа по монтажу, этап № 1"
    assert result.status == "OK"


def test_leading_zero_code_is_preserved():
    assert parse_text_value("00123").value == "00123"


def test_empty_and_unsupported_text():
    assert parse_text_value(None).status == "EMPTY"
    assert parse_text_value(" \n ").status == "EMPTY"
    assert parse_text_value(True).status == "UNSUPPORTED_VALUE_TYPE"
