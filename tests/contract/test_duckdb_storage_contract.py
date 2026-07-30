"""Public contract for the primary DuckDB working store."""

from report_processor.storage import (
    MAX_QUERY_LIMIT,
    SCHEMA_VERSION,
    DuckDBStore,
    StorageError,
    StorageExportResult,
    StorageMigrationError,
    StorageQuery,
    StorageQueryError,
    StorageSchemaError,
    StorageWriteError,
    StorageWriteResult,
)


def test_duckdb_storage_public_api_is_importable():
    assert SCHEMA_VERSION == 1
    assert MAX_QUERY_LIMIT == 10_000
    assert DuckDBStore.__name__ == "DuckDBStore"
    assert StorageQuery.__name__ == "StorageQuery"
    assert StorageWriteResult.__name__ == "StorageWriteResult"
    assert StorageExportResult.__name__ == "StorageExportResult"
    assert issubclass(StorageMigrationError, StorageError)
    assert issubclass(StorageQueryError, StorageError)
    assert issubclass(StorageSchemaError, StorageError)
    assert issubclass(StorageWriteError, StorageError)
