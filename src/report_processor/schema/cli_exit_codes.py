"""Centralized detect-schema CLI exit codes."""

from enum import IntEnum


class DetectSchemaExitCode(IntEnum):
    OK = 0
    SOURCE_NOT_FOUND = 2
    WORKBOOK_OPEN_ERROR = 3
    SHEET_NOT_FOUND = 4
    STRUCTURE_NOT_RECOGNIZED = 5
    AMBIGUOUS_STRUCTURE = 6
    LOW_CONFIDENCE = 7
    SAVE_ERROR = 8
    INVALID_ARGUMENTS = 9
