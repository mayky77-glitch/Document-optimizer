"""Тесты классификации файлов по имени."""

import pytest

from report_processor.inventory.file_classifier import classify_file_by_name


@pytest.mark.parametrize(
    ("filename", "document_type"),
    [
        ("1006 (682)_КС-2_КС-3_КС-6а июль 2026 ред2.xlsx", "ks6a"),
        ("0842 (623)_КС 6А июль.xlsx", "ks6a"),
        ("report_KS-6A.xlsx", "ks6a"),
        ("КС-2 июль.xlsx", "ks2"),
        ("КС-3 июль.xlsx", "ks3"),
        ("СВВР июль 2026.xlsx", "svvr"),
        ("сводная ведомость выполненных работ.xlsx", "svvr"),
        ("ДОПОТЧЕТ ИЮЛЬ_ИТОГ.xlsx", "additional_report"),
        ("РАСЧЕТ ДОП.ОТЧЕТА.xlsx", "additional_report"),
        ("обычный файл.xlsx", "unknown"),
        ("Реестр КС-2 июль.xlsx", "ks2_registry"),
        ("Перечень подобъектов.xlsx", "subobject_reference"),
        ("ВиСР вар.1.xlsx", "visr"),
        ("ДРДЦ 10 2025.xlsx", "drdc"),
        ("пакет КС-2.zip", "archive"),
    ],
)
def test_classification_variants(filename: str, document_type: str) -> None:
    assert classify_file_by_name(filename).document_type == document_type


def test_multiple_markers_are_preserved() -> None:
    result = classify_file_by_name("1006 (682)_КС-2_КС-3_КС-6а июль 2026 ред2.xlsx")

    assert result.document_type == "ks6a"
    assert result.document_markers == ["ks6a", "ks2", "ks3"]


def test_document_index_is_not_copy_suffix() -> None:
    result = classify_file_by_name("1006 (682)_КС-2.xlsx")

    assert result.is_probable_copy is False


def test_numeric_suffix_near_end_is_probable_copy() -> None:
    result = classify_file_by_name("копия КС-6а (1).xlsx")

    assert result.is_probable_copy is True
    assert result.document_type == "ks6a"


def test_temporary_file_is_detected() -> None:
    result = classify_file_by_name("~$КС-6а.xlsx")

    assert result.is_temporary is True
    assert result.document_type == "ks6a"


@pytest.mark.parametrize("filename", ["6а.xlsx", "6a.xlsx", "КС_6а.xlsx", "KS 6A.xlsx"])
def test_ks6a_without_false_negative(filename: str) -> None:
    assert classify_file_by_name(filename).document_type == "ks6a"


def test_plain_six_is_not_ks6a() -> None:
    assert classify_file_by_name("отчет 6.xlsx").document_type == "unknown"


def test_generic_vedomost_is_not_svvr() -> None:
    assert classify_file_by_name("ведомость материалов.xlsx").document_type == "unknown"


def test_zip_named_archive_is_container_not_outdated() -> None:
    result = classify_file_by_name("архив.zip")

    assert result.document_type == "archive"
    assert result.is_probably_outdated is False


def test_appledouble_metadata_is_temporary() -> None:
    result = classify_file_by_name("._КС-2.xlsx")

    assert result.is_temporary is True
