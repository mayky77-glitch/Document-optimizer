"""Контролируемые исключения блока инвентаризации."""

from pathlib import Path

from report_processor.domain.statuses import StatusCode


class InventoryError(Exception):
    """Базовая ошибка инвентаризации с машинно-читаемым кодом."""

    status_code: StatusCode = StatusCode.WARNING


class SourceNotFoundError(InventoryError):
    """Источник данных не существует."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Источник не найден: {path}")


class SourceAccessError(InventoryError):
    """Источник невозможно прочитать или исследовать."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        super().__init__(f"Невозможно открыть источник {path}: {reason}")


class BrokenArchiveError(InventoryError):
    """ZIP-архив повреждён или имеет неподдерживаемую структуру."""

    status_code = StatusCode.BROKEN_ARCHIVE

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        super().__init__(f"Повреждённый ZIP-архив {path}: {reason}")


class ManifestWriteError(InventoryError):
    """Манифест не удалось записать атомарно."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        super().__init__(f"Не удалось записать манифест {path}: {reason}")


class ManifestReadError(InventoryError):
    """Манифест не удалось прочитать или восстановить в типизированную модель."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        super().__init__(f"Не удалось прочитать манифест {path}: {reason}")
