from report_processor.schema.text_normalization import normalize_header_text


def test_required_normalization_examples() -> None:
    assert normalize_header_text(" Ед. изм. ") == "единица измерения"
    assert normalize_header_text("ЕДИНИЦА\nИЗМЕРЕНИЯ") == "единица измерения"
    assert normalize_header_text("Наименование   работ") == "наименование работ"
    assert normalize_header_text("ОБЪЁМ ЗА ИЮЛЬ 2026") == "объем за июль 2026"
    assert normalize_header_text("Стоимость, руб.") == "стоимость руб"
    assert normalize_header_text("млн. руб.") == "млн руб"


def test_semantic_differences_are_preserved() -> None:
    quantity = normalize_header_text("Количество за июль 2026")
    price = normalize_header_text("Цена за единицу, руб.")
    cost = normalize_header_text("Стоимость за июль 2026")
    assert quantity != price != cost
    assert "2026" in quantity
