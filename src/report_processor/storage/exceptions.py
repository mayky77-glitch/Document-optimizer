from __future__ import annotations


class StorageError(Exception):
    """Base error for controlled working-store failures."""


class StorageMigrationError(StorageError):
    """The database could not be created or migrated safely."""


class StorageSchemaError(StorageError):
    """The database schema is corrupt or newer than this application supports."""


class StorageWriteError(StorageError):
    """A row batch could not be committed atomically."""


class StorageQueryError(StorageError):
    """A storage read could not be completed."""


class StorageExportError(StorageError):
    """A JSONL export could not be written."""
