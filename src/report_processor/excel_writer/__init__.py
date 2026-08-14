"""Atomic, no-clobber XLSX publication (ExcelWriterEngine-15.1)."""

from .engine import write_target_report
from .exceptions import (
    ExcelWriterAtomicError,
    ExcelWriterError,
    ExcelWriterInputError,
    ExcelWriterIntegrityError,
    ExcelWriterSafetyError,
)
from .models import (
    EXCEL_WRITER_CONTRACT_VERSION,
    EXCEL_WRITER_ENGINE_VERSION,
    WriteResult,
    WriteStatus,
    WrittenCell,
)
from .row_annotations import annotate_failed_rows

__all__ = (
    "EXCEL_WRITER_CONTRACT_VERSION",
    "EXCEL_WRITER_ENGINE_VERSION",
    "ExcelWriterAtomicError",
    "ExcelWriterError",
    "ExcelWriterInputError",
    "ExcelWriterIntegrityError",
    "ExcelWriterSafetyError",
    "WriteResult",
    "WriteStatus",
    "WrittenCell",
    "annotate_failed_rows",
    "build_period_insertion_plan",
    "prepare_period_insertion",
    "verify_period_insertion",
    "write_target_report",
)


def __getattr__(name: str):
    """Load period transformation only for callers that explicitly request it."""
    if name in {
        "build_period_insertion_plan",
        "prepare_period_insertion",
        "verify_period_insertion",
    }:
        from . import period_insertion

        return getattr(period_insertion, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
