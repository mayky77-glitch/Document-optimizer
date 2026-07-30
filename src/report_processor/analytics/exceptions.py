"""Controlled failures for the analytical DuckDB contract."""

from __future__ import annotations


class AnalyticalError(Exception):
    """Base error for AnalyticalStore-11.0 operations."""


class AnalyticalMigrationError(AnalyticalError):
    """The analytical database cannot be safely created or migrated."""


class AnalyticalSchemaError(AnalyticalError):
    """The analytical database does not match AnalyticalSchema-1."""


class AnalyticalWriteError(AnalyticalError):
    """An atomic analytical load could not be completed."""


class AnalyticalQueryError(AnalyticalError):
    """A bounded named analytical query is invalid or cannot be run."""


class AnalyticalExportError(AnalyticalError):
    """The deterministic diagnostics export could not be completed."""
