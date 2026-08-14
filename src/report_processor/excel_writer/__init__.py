"""Atomic, no-clobber XLSX publication (ExcelWriterEngine-15.1)."""

from importlib import import_module

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

_LAZY_PERIOD_EXPORTS = frozenset(
    {
        "build_period_insertion_plan",
        "prepare_period_insertion",
        "verify_period_insertion",
    }
)

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
    if name in _LAZY_PERIOD_EXPORTS:
        value = getattr(import_module(".period_insertion", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
