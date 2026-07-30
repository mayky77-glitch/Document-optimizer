from __future__ import annotations

from enum import Enum


class CellValueStatus(str, Enum):
    OK = "OK"
    EMPTY = "EMPTY"
    FORMULA_WITH_CACHED_VALUE = "FORMULA_WITH_CACHED_VALUE"
    FORMULA_WITHOUT_CACHED_VALUE = "FORMULA_WITHOUT_CACHED_VALUE"
    EXCEL_ERROR = "EXCEL_ERROR"
    UNSUPPORTED_VALUE_TYPE = "UNSUPPORTED_VALUE_TYPE"
    VALUE_READ_FAILED = "VALUE_READ_FAILED"


class EffectiveValueSource(str, Enum):
    LITERAL = "literal"
    CACHED_FORMULA_VALUE = "cached_formula_value"
    FORMULA_WITHOUT_CACHE = "formula_without_cache"
    EXCEL_ERROR = "excel_error"
    EMPTY = "empty"


class NumericValueStatus(str, Enum):
    OK = "OK"
    EMPTY = "EMPTY"
    INVALID_FORMAT = "INVALID_FORMAT"
    UNSUPPORTED_VALUE_TYPE = "UNSUPPORTED_VALUE_TYPE"
    NON_FINITE = "NON_FINITE"
    TEXT_NUMBERS_DISABLED = "TEXT_NUMBERS_DISABLED"


class TextValueStatus(str, Enum):
    OK = "OK"
    EMPTY = "EMPTY"
    UNSUPPORTED_VALUE_TYPE = "UNSUPPORTED_VALUE_TYPE"


class AdapterValidationStatus(str, Enum):
    OK = "OK"
    WRONG_SHEET_TYPE = "WRONG_SHEET_TYPE"
    REQUIRED_COLUMNS_MISSING = "REQUIRED_COLUMNS_MISSING"
    OPTIONAL_COLUMNS_MISSING = "OPTIONAL_COLUMNS_MISSING"
    SCHEMA_INVALID = "SCHEMA_INVALID"


class CanonicalRowStatus(str, Enum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"
    EMPTY = "EMPTY"


class ExtractionStatus(str, Enum):
    OK = "OK"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    ADAPTER_NOT_AVAILABLE = "ADAPTER_NOT_AVAILABLE"
    REQUIRED_COLUMNS_MISSING = "REQUIRED_COLUMNS_MISSING"
    ROW_LIMIT_REACHED = "ROW_LIMIT_REACHED"
    EMPTY_ROW_LIMIT_REACHED = "EMPTY_ROW_LIMIT_REACHED"
    NO_ROWS_EXTRACTED = "NO_ROWS_EXTRACTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class StopReason(str, Enum):
    REPORTED_END_REACHED = "reported_end_reached"
    ROW_LIMIT_REACHED = "row_limit_reached"
    EMPTY_ROW_LIMIT_REACHED = "empty_row_limit_reached"
    ERROR = "error"


class IssueSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"
