"""Atomic structured audit artifact writers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as stream:
        json.dump(to_jsonable(value), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temp_path = Path(stream.name)
    os.replace(temp_path, path)


def atomic_write_jsonl(path: Path, values: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as stream:
        for value in values:
            stream.write(json.dumps(to_jsonable(value), ensure_ascii=False) + "\n")
        temp_path = Path(stream.name)
    os.replace(temp_path, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hashes(paths: Iterable[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in dict.fromkeys(item.resolve() for item in paths if item.exists() and item.is_file()):
        result[str(path)] = sha256_file(path)
    return result


class AtomicJsonlWriter:
    """Incremental JSONL writer that atomically publishes on successful exit."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream = None
        self._temp_path: Path | None = None

    def __enter__(self) -> AtomicJsonlWriter:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=self.path.name + ".",
            suffix=".tmp",
            dir=self.path.parent,
            delete=False,
        )
        self._temp_path = Path(self._stream.name)
        return self

    def write(self, value: Any) -> None:
        if self._stream is None:
            raise RuntimeError("AtomicJsonlWriter is not open")
        self._stream.write(json.dumps(to_jsonable(value), ensure_ascii=False) + "\n")

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if self._stream is None or self._temp_path is None:
            return False
        self._stream.close()
        if exc_type is None:
            os.replace(self._temp_path, self.path)
        else:
            self._temp_path.unlink(missing_ok=True)
        self._stream = None
        self._temp_path = None
        return False
