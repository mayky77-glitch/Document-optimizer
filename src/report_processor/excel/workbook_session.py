from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from report_processor.domain.exceptions import (
    WorkbookSessionClosedError,
    WorkbookViewMismatchError,
)
from report_processor.domain.statuses import StatusCode

from .models import DualWorkbookSession, WorkbookOpenRequest
from .workbook_loader import load_dual_workbooks

LOGGER = logging.getLogger(__name__)


def validate_dual_workbook_session(session: DualWorkbookSession) -> tuple[str, ...]:
    if session.closed:
        raise WorkbookSessionClosedError(
            StatusCode.WORKBOOK_SESSION_CLOSED,
            "Workbook-сессия уже закрыта",
        )
    if session.formula_workbook is None or session.value_workbook is None:
        raise WorkbookViewMismatchError(
            StatusCode.WORKBOOK_VIEW_MISMATCH,
            "Одна из workbook-проекций отсутствует",
        )
    if session.formula_source_path != session.value_source_path:
        raise WorkbookViewMismatchError(
            StatusCode.WORKBOOK_VIEW_MISMATCH,
            "Workbook-проекции относятся к разным локальным файлам",
        )

    formula_names = tuple(session.formula_workbook.sheetnames)
    value_names = tuple(session.value_workbook.sheetnames)
    if formula_names != value_names:
        raise WorkbookViewMismatchError(
            StatusCode.WORKBOOK_VIEW_MISMATCH,
            "Списки листов двух workbook-проекций различаются",
        )

    formula_has_vba = getattr(session.formula_workbook, "vba_archive", None) is not None
    value_has_vba = getattr(session.value_workbook, "vba_archive", None) is not None
    if formula_has_vba != value_has_vba or formula_has_vba != session.keep_vba:
        raise WorkbookViewMismatchError(
            StatusCode.WORKBOOK_VIEW_MISMATCH,
            "Параметр keep_vba применён несогласованно",
        )
    return ()


@contextmanager
def open_dual_workbook(request: WorkbookOpenRequest) -> Iterator[DualWorkbookSession]:
    session = load_dual_workbooks(request)
    try:
        validate_dual_workbook_session(session)
        yield session
    finally:
        session.close()
        LOGGER.info("Обе workbook-проекции успешно закрыты")
