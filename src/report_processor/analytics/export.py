"""Atomic, deterministic diagnostics JSONL rendering."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .exceptions import AnalyticalExportError


def write_diagnostics_temp(
    output: Path, records: Iterable[Mapping[str, Any]]
) -> tuple[Path, int, int]:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            count = 0
            for record in records:
                stream.write(
                    json.dumps(
                        dict(record),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                )
                stream.write("\n")
                count += 1
            stream.flush()
            os.fsync(stream.fileno())
        return temporary, count, temporary.stat().st_size
    except (OSError, TypeError, ValueError) as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise AnalyticalExportError(f"Не удалось подготовить diagnostics JSONL: {exc}") from exc
