from __future__ import annotations


class ExtractionError(Exception):
    pass


class AdapterNotAvailableError(ExtractionError):
    pass


class ExtractionSchemaError(ExtractionError):
    pass


class RowReadError(ExtractionError):
    pass


class ExtractionSerializationError(ExtractionError):
    pass
