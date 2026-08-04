from decimal import Decimal
from pathlib import PurePosixPath

import pytest

from report_processor.package_reconciliation.matcher import (
    drawing_codes_for_row,
    reconcile_row,
)
from report_processor.package_reconciliation.models import WorkbookRowFact
from report_processor.package_reconciliation.pdf_documents import PdfDocumentEvidence


def _row(number: int, code: str, *, drawing: str | None = None) -> WorkbookRowFact:
    return WorkbookRowFact(
        "Лист",
        number,
        None,
        None,
        None,
        code,
        drawing,
        None,
        "Устройство основания",
        "м",
        Decimal("6250"),
        None,
    )


def _pdf(*, quantity: str = "6.25", unit: str = "км") -> PdfDocumentEvidence:
    return PdfDocumentEvidence(
        PurePosixPath("2.4.6.8.10/АОСР.pdf"),
        "aosr",
        1,
        "text_layer",
        None,
        None,
        ("DEMO.321.PROJ-123",),
        "Устройство основания",
        (quantity,),
        (unit,),
        None,
        (),
    )


def test_uses_nearest_preceding_dotted_parent_drawing_only() -> None:
    grandparent = _row(5, "2.4", drawing="WRONG")
    parent = _row(9, "2.4.6.8", drawing="DEMO.321.PROJ-123")
    detail = _row(10, "2.4.6.8.10")
    sibling = _row(11, "2.4.6.9", drawing="SIBLING")

    assert drawing_codes_for_row(detail, (grandparent, parent, detail, sibling)) == (
        "DEMO.321.PROJ-123",
    )


def test_requires_content_signal_and_converts_m_to_km() -> None:
    parent = _row(9, "2.4.6.8", drawing="DEMO.321.PROJ-123")
    detail = _row(10, "2.4.6.8.10")

    result = reconcile_row(
        detail,
        PurePosixPath("акт.xlsx"),
        (_pdf(),),
        drawing_codes=drawing_codes_for_row(detail, (parent, detail)),
    )

    assert result.status == "MATCH"
    assert result.quantity_comparison == "MATCH"
    assert result.cost_comparison == "NOT_COMPARABLE"
    assert result.workbook_quantity == Decimal("6250")


def test_does_not_match_from_basename_or_without_signal() -> None:
    candidate = PdfDocumentEvidence(
        PurePosixPath("2.4.6.8.10/АОСР.pdf"),
        "aosr",
        1,
        "text_layer",
        None,
        None,
        (),
        None,
        (),
        (),
        None,
        (),
    )
    result = reconcile_row(_row(10, "2.4.6.8.10"), PurePosixPath("акт.xlsx"), (candidate,))

    assert result.status == "NEEDS_REVIEW"
    assert result.pdf_path is None
    assert result.reason_codes == ("independent_content_signal_missing",)


def test_equal_candidates_are_ambiguous_and_quantity_mismatch_is_reported() -> None:
    detail = _row(10, "2.4.6.8.10")
    candidate = _pdf(quantity="5.5")
    other = PdfDocumentEvidence(
        PurePosixPath("2.4.6.8.10/АОСР-2.pdf"),
        "aosr",
        1,
        "text_layer",
        None,
        None,
        candidate.project_codes,
        candidate.work_description,
        candidate.quantity_candidates,
        candidate.unit_candidates,
        None,
        (),
    )
    context = ("DEMO.321.PROJ-123",)

    assert (
        reconcile_row(
            detail, PurePosixPath("акт.xlsx"), (candidate, other), drawing_codes=context
        ).status
        == "AMBIGUOUS"
    )
    assert (
        reconcile_row(detail, PurePosixPath("акт.xlsx"), (candidate,), drawing_codes=context).status
        == "MISMATCH"
    )


def test_project_code_signal_accepts_long_excel_code_and_shorter_pdf_backbone() -> None:
    detail = _row(10, "2.4.6.8.10")
    candidate = _pdf()

    result = reconcile_row(
        detail,
        PurePosixPath("акт.xlsx"),
        (candidate,),
        drawing_codes=("DEMO.321.PROJ-123.SHEET-7; unrelated",),
    )

    assert result.status == "MATCH"
    assert "project_code_match" in result.reason_codes


def test_project_code_requires_complete_components_and_prefers_own_drawing() -> None:
    parent = _row(9, "2.4.6", drawing="SYN.101.CD-3")
    detail = _row(10, "2.4.6.8", drawing="SYN.202.EF-4.5")
    matching = PdfDocumentEvidence(
        PurePosixPath("2.4.6.8/АОСР.pdf"),
        "aosr",
        1,
        "text_layer",
        None,
        None,
        ("SYN.202.EF-4",),
        "Устройство основания",
        (),
        (),
        None,
        (),
    )
    last_component_prefix = PdfDocumentEvidence(
        PurePosixPath("2.4.6.8/АОСР-2.pdf"),
        "aosr",
        1,
        "text_layer",
        None,
        None,
        ("SYN.202.EF-45",),
        None,
        (),
        (),
        None,
        (),
    )

    assert drawing_codes_for_row(detail, (parent, detail)) == ("SYN.202.EF-4.5",)
    assert (
        reconcile_row(
            detail,
            PurePosixPath("акт.xlsx"),
            (matching,),
            drawing_codes=drawing_codes_for_row(detail, (parent, detail)),
        ).status
        == "MATCH"
    )
    assert (
        reconcile_row(
            detail,
            PurePosixPath("акт.xlsx"),
            (last_component_prefix,),
            drawing_codes=drawing_codes_for_row(detail, (parent, detail)),
        ).status
        == "NEEDS_REVIEW"
    )


def test_reconciliation_rejects_absolute_or_traversal_paths() -> None:
    with pytest.raises(ValueError, match="safe and relative"):
        reconcile_row(_row(1, "1.1"), PurePosixPath("../акт.xlsx"), ())


def test_project_code_signal_ranks_above_generic_work_name_similarity() -> None:
    detail = _row(10, "2.4.6.8.10")
    project_candidate = _pdf()
    generic_candidate = PdfDocumentEvidence(
        PurePosixPath("2.4.6.8.10/АОСР-2.pdf"),
        "aosr",
        1,
        "text_layer",
        None,
        None,
        (),
        "Устройство основания",
        (),
        (),
        None,
        (),
    )

    result = reconcile_row(
        detail,
        PurePosixPath("акт.xlsx"),
        (project_candidate, generic_candidate),
        drawing_codes=("DEMO.321.PROJ-123",),
    )

    assert result.status == "MATCH"
    assert result.pdf_path == project_candidate.relative_path
