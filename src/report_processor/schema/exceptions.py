"""Exceptional failures, distinct from expected uncertain detection states."""


class SchemaDetectionError(Exception):
    pass


class WorksheetScanError(SchemaDetectionError):
    pass


class HeaderDetectionError(SchemaDetectionError):
    pass


class ColumnResolutionError(SchemaDetectionError):
    pass
