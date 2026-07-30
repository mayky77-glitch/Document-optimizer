"""Controlled failures for the immutable XLSX writer."""

from __future__ import annotations


class ExcelWriterError(ValueError):
    code = "EXCEL_WRITER_ERROR"

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class ExcelWriterInputError(ExcelWriterError):
    """The supplied immutable artifacts cannot form a safe write plan."""


class ExcelWriterSafetyError(ExcelWriterError):
    """A filesystem or package safety precondition was not met."""


class ExcelWriterIntegrityError(ExcelWriterError):
    """A source identity or preservation invariant changed."""


class ExcelWriterAtomicError(ExcelWriterError):
    """The output could not be published atomically without clobbering."""
