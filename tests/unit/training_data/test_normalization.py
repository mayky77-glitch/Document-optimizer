from report_processor.training_data import normalize_code, normalize_text, normalize_unit


def test_normalizes_text_whitespace_unicode_and_case():
    assert normalize_text("  Монтаж\u00a0  ТРУБ Ёлка ") == "монтаж труб елка"


def test_normalizes_units_conservatively():
    assert normalize_unit("кв. м") == "м²"
    assert normalize_unit("м3") == "м³"
    assert normalize_unit("ШТ.") == "шт"
    assert normalize_unit("маш.-ч") == "маш.-ч"


def test_normalizes_number_sign_in_codes():
    assert normalize_code("No.  15 ") == "№ 15"
    assert normalize_code("№15") == "№ 15"
