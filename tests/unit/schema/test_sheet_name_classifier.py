import pytest

from report_processor.schema.models import SheetType
from report_processor.schema.sheet_name_classifier import classify_sheet_name


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("КС-2", SheetType.KS2),
        ("КС 2", SheetType.KS2),
        ("КС-3", SheetType.KS3),
        ("КС-6а", SheetType.KS6A),
        ("KS-6A", SheetType.KS6A),
        ("СВВР", SheetType.SVVR),
        ("Реестр КС-2", SheetType.KS2_REGISTRY),
        ("ДОПОТЧЕТ", SheetType.ADDITIONAL_REPORT),
        ("Титульный", SheetType.TITLE),
        ("КС-2 старый", SheetType.KS2),
        ("КС-6а корректировка", SheetType.KS6A),
    ],
)
def test_sheet_name_variants(name: str, expected: SheetType) -> None:
    assert classify_sheet_name(name)[0].sheet_type == expected


def test_uninformative_sheet_name_has_no_candidate() -> None:
    assert classify_sheet_name("Лист1") == ()
    assert classify_sheet_name("Sheet1") == ()


def test_registry_is_not_plain_ks2() -> None:
    candidates = classify_sheet_name("Реестр КС-2")
    assert candidates[0].sheet_type == SheetType.KS2_REGISTRY
    assert candidates[0].score > candidates[1].score
