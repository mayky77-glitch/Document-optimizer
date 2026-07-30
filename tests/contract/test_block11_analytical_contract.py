"""Frozen public contract for AnalyticalStore-11.0 / AnalyticalSchema-1."""

from report_processor.analytics import (
    ANALYTICAL_CONTRACT_VERSION,
    ANALYTICAL_SCHEMA_VERSION,
    AnalyticalError,
    AnalyticalExportResult,
    AnalyticalLoadResult,
    AnalyticalQuery,
    AnalyticalQueryError,
    AnalyticalQueryResult,
    AnalyticalSchemaError,
    AnalyticalStore,
    AnalyticalWriteError,
)


def test_public_api_and_versions_are_importable():
    assert ANALYTICAL_CONTRACT_VERSION == "AnalyticalStore-11.0"
    assert ANALYTICAL_SCHEMA_VERSION == "AnalyticalSchema-1"
    assert all(
        callable(getattr(AnalyticalStore, method))
        for method in (
            "load_source_rows",
            "load_target_rows",
            "load_rule_set",
            "query",
            "export_diagnostics_jsonl",
        )
    )
    assert all(
        item.__name__.startswith("Analytical")
        for item in (
            AnalyticalLoadResult,
            AnalyticalQuery,
            AnalyticalQueryResult,
            AnalyticalExportResult,
        )
    )
    assert issubclass(AnalyticalQueryError, AnalyticalError)
    assert issubclass(AnalyticalSchemaError, AnalyticalError)
    assert issubclass(AnalyticalWriteError, AnalyticalError)
