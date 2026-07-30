from __future__ import annotations

from enum import StrEnum


class CellValueStatus(StrEnum):
    OK = "OK"
    EMPTY = "EMPTY"
    FORMULA_WITH_CACHED_VALUE = "FORMULA_WITH_CACHED_VALUE"
    FORMULA_WITHOUT_CACHED_VALUE = "FORMULA_WITHOUT_CACHED_VALUE"
    EXCEL_ERROR = "EXCEL_ERROR"
    UNSUPPORTED_VALUE_TYPE = "UNSUPPORTED_VALUE_TYPE"
    VALUE_READ_FAILED = "VALUE_READ_FAILED"


class EffectiveValueSource(StrEnum):
    LITERAL = "literal"
    CACHED_FORMULA_VALUE = "cached_formula_value"
    FORMULA_WITHOUT_CACHE = "formula_without_cache"
    EXCEL_ERROR = "excel_error"
    EMPTY = "empty"


class NumericValueStatus(StrEnum):
    OK = "OK"
    EMPTY = "EMPTY"
    INVALID_FORMAT = "INVALID_FORMAT"
    UNSUPPORTED_VALUE_TYPE = "UNSUPPORTED_VALUE_TYPE"
    NON_FINITE = "NON_FINITE"
    TEXT_NUMBERS_DISABLED = "TEXT_NUMBERS_DISABLED"


class TextValueStatus(StrEnum):
    OK = "OK"
    EMPTY = "EMPTY"
    UNSUPPORTED_VALUE_TYPE = "UNSUPPORTED_VALUE_TYPE"


class AdapterValidationStatus(StrEnum):
    OK = "OK"
    WRONG_SHEET_TYPE = "WRONG_SHEET_TYPE"
    REQUIRED_COLUMNS_MISSING = "REQUIRED_COLUMNS_MISSING"
    OPTIONAL_COLUMNS_MISSING = "OPTIONAL_COLUMNS_MISSING"
    SCHEMA_INVALID = "SCHEMA_INVALID"


class CanonicalRowStatus(StrEnum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"
    EMPTY = "EMPTY"


class ExtractionStatus(StrEnum):
    OK = "OK"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    ADAPTER_NOT_AVAILABLE = "ADAPTER_NOT_AVAILABLE"
    REQUIRED_COLUMNS_MISSING = "REQUIRED_COLUMNS_MISSING"
    ROW_LIMIT_REACHED = "ROW_LIMIT_REACHED"
    EMPTY_ROW_LIMIT_REACHED = "EMPTY_ROW_LIMIT_REACHED"
    NO_ROWS_EXTRACTED = "NO_ROWS_EXTRACTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class StopReason(StrEnum):
    REPORTED_END_REACHED = "reported_end_reached"
    ROW_LIMIT_REACHED = "row_limit_reached"
    EMPTY_ROW_LIMIT_REACHED = "empty_row_limit_reached"
    ERROR = "error"


class IssueSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"
