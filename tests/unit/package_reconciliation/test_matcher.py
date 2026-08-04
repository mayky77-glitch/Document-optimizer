from decimal import Decimal
from pathlib import PurePosixPath

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
        Decimal("5513"),
        None,
    )


def _pdf(*, quantity: str = "5.513", unit: str = "км") -> PdfDocumentEvidence:
    return PdfDocumentEvidence(
        PurePosixPath("6.1.10.1.1/АОСР.pdf"),
        "aosr",
        1,
        "text_layer",
        None,
        None,
        ("0092.049.Р-123",),
        "Устройство основания",
        (quantity,),
        (unit,),
        None,
        (),
    )


def test_uses_nearest_preceding_dotted_parent_drawing_only() -> None:
    grandparent = _row(5, "6.1", drawing="WRONG")
    parent = _row(9, "6.1.10.1", drawing="0092.049.Р-123")
    detail = _row(10, "6.1.10.1.1")
    sibling = _row(11, "6.1.10.2", drawing="SIBLING")

    assert drawing_codes_for_row(detail, (grandparent, parent, detail, sibling)) == (
        "0092.049.Р-123",
    )


def test_requires_content_signal_and_converts_m_to_km() -> None:
    parent = _row(9, "6.1.10.1", drawing="0092.049.Р-123")
    detail = _row(10, "6.1.10.1.1")

    result = reconcile_row(
        detail,
        PurePosixPath("акт.xlsx"),
        (_pdf(),),
        drawing_codes=drawing_codes_for_row(detail, (parent, detail)),
    )

    assert result.status == "MATCH"
    assert result.quantity_comparison == "MATCH"
    assert result.cost_comparison == "NOT_COMPARABLE"
    assert result.workbook_quantity == Decimal("5513")


def test_does_not_match_from_basename_or_without_signal() -> None:
    candidate = PdfDocumentEvidence(
        PurePosixPath("6.1.10.1.1/АОСР.pdf"),
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
    result = reconcile_row(_row(10, "6.1.10.1.1"), PurePosixPath("акт.xlsx"), (candidate,))

    assert result.status == "NEEDS_REVIEW"
    assert result.pdf_path is None
    assert result.reason_codes == ("independent_content_signal_missing",)


def test_equal_candidates_are_ambiguous_and_quantity_mismatch_is_reported() -> None:
    detail = _row(10, "6.1.10.1.1")
    candidate = _pdf(quantity="5.5")
    other = PdfDocumentEvidence(
        PurePosixPath("6.1.10.1.1/АОСР-2.pdf"),
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
    context = ("0092.049.Р-123",)

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
