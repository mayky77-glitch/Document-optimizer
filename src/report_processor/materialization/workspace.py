from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from types import TracebackType

from report_processor.domain.exceptions import MaterializationError
from report_processor.domain.statuses import StatusCode

LOGGER = logging.getLogger(__name__)


class TemporaryWorkspace:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else None
        self.path: Path | None = None
        self.cleanup_warnings: list[str] = []
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> Path:
        try:
            if self.root is not None:
                self.root.mkdir(parents=True, exist_ok=True)
            self._temporary_directory = tempfile.TemporaryDirectory(
                prefix="report-processor-", dir=self.root
            )
            self.path = Path(self._temporary_directory.name)
            LOGGER.debug("Temporary workspace created: %s", self.path)
            return self.path
        except OSError as error:
            raise MaterializationError(
                StatusCode.WORKSPACE_CREATION_FAILED,
                f"Не удалось создать временную область: {error}",
            ) from error

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self._temporary_directory is None:
            return False
        try:
            self._temporary_directory.cleanup()
            LOGGER.info("Временная область очищена")
        except OSError as error:
            self.cleanup_warnings.append(StatusCode.CLEANUP_FAILED.value)
            LOGGER.warning("Не удалось полностью очистить временную область: %s", error)
            if exc is None:
                raise MaterializationError(
                    StatusCode.CLEANUP_FAILED,
                    f"Не удалось очистить временную область: {error}",
                ) from error
        finally:
            self.path = None
            self._temporary_directory = None
        return False
