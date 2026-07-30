"""Frozen public contract for AnalyticalStore-11.0 / AnalyticalSchema-1."""

from report_processor.analytics import (
    ANALYTICAL_MAX_QUERY_LIMIT,
    ANALYTICAL_SCHEMA_VERSION,
    AnalyticalExportResult,
    AnalyticalLoadResult,
    AnalyticalQuery,
    AnalyticalRuleSet,
    AnalyticalSchemaError,
    AnalyticalSourceRow,
    AnalyticalStore,
    AnalyticalStoreError,
    AnalyticalTargetRow,
    AnalyticalWriteError,
)


def test_block11_public_api_is_importable_and_versioned():
    assert ANALYTICAL_SCHEMA_VERSION == 1
    assert ANALYTICAL_MAX_QUERY_LIMIT == 10_000
    assert AnalyticalStore.__name__ == "AnalyticalStore"
    assert AnalyticalQuery.__name__ == "AnalyticalQuery"
    assert AnalyticalSourceRow.__name__ == "AnalyticalSourceRow"
    assert AnalyticalTargetRow.__name__ == "AnalyticalTargetRow"
    assert AnalyticalRuleSet.__name__ == "AnalyticalRuleSet"
    assert AnalyticalLoadResult.__name__ == "AnalyticalLoadResult"
    assert AnalyticalExportResult.__name__ == "AnalyticalExportResult"
    assert issubclass(AnalyticalSchemaError, AnalyticalStoreError)
    assert issubclass(AnalyticalWriteError, AnalyticalStoreError)


def test_block11_public_methods_are_explicit_and_separated():
    for method in (
        "load_source_rows",
        "load_target_rows",
        "load_rule_set",
        "query",
        "export_diagnostics_jsonl",
        "close",
    ):
        assert callable(getattr(AnalyticalStore, method))
