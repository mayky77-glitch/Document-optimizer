"""Small dependency-free terminal interface for the drawing-card CLI."""

from __future__ import annotations

import os
import shlex
from collections.abc import Callable
from pathlib import Path

CliMain = Callable[[list[str] | None], int]


class _Color:
    BLUE = "\033[38;5;33m"
    GREEN = "\033[38;5;34m"
    YELLOW = "\033[38;5;214m"
    RED = "\033[38;5;196m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def _supports_color() -> bool:
    return os.getenv("NO_COLOR") is None and os.isatty(1)


def _paint(text: str, *styles: str) -> str:
    if not _supports_color():
        return text
    return "".join(styles) + text + _Color.RESET


def _clear() -> None:
    if os.isatty(1):
        print("\033[2J\033[H", end="")


def _banner() -> None:
    print(_paint("╔══════════════════════════════════════════════════════════╗", _Color.BLUE))
    print(
        _paint(
            "║       КАРТОЧКА ОСТАТКОВ — БЕЗОПАСНЫЙ ПОМОЩНИК          ║", _Color.BLUE, _Color.BOLD
        )
    )
    print(_paint("╚══════════════════════════════════════════════════════════╝", _Color.BLUE))
    print(_paint("Файлы-источники не изменяются. Каждый запуск сохраняет аудит.\n", _Color.DIM))


def _choice(title: str, options: tuple[tuple[str, str], ...]) -> str:
    print(_paint(title, _Color.BOLD))
    for key, label in options:
        print(f"  {_paint(key, _Color.GREEN)}. {label}")
    allowed = {key for key, _label in options}
    while True:
        value = input("Выберите пункт: ").strip()
        if value in allowed:
            return value
        print(_paint("Введите номер из списка.", _Color.YELLOW))


def _clean_dragged_path(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        parts = shlex.split(value)
    except ValueError:
        parts = []
    if len(parts) == 1:
        return parts[0]
    return value.strip("'\"").replace("\\ ", " ")


def _path(prompt: str, *, default: str | None = None, must_exist: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"{prompt}{suffix}: ")
        value = _clean_dragged_path(raw) or (default or "")
        if not value:
            print(_paint("Путь не должен быть пустым.", _Color.YELLOW))
            continue
        expanded = Path(value).expanduser()
        if must_exist and not expanded.exists():
            print(_paint(f"Файл или папка не найдены: {expanded}", _Color.RED))
            continue
        return str(expanded)


def _xlsx_output_path(prompt: str, *, default: str, default_filename: str) -> str:
    """Accept either a full XLSX path or an existing directory."""
    while True:
        value = _path(prompt, default=default)
        path = Path(value).expanduser()
        if path.exists() and path.is_dir():
            resolved = path / default_filename
            print(_paint(f"Файл будет сохранён как: {resolved}", _Color.BLUE))
            return str(resolved)
        if path.suffix.lower() != ".xlsx":
            print(
                _paint(
                    "Укажите имя файла с расширением .xlsx или существующую папку.",
                    _Color.YELLOW,
                )
            )
            continue
        return str(path)


def _optional(prompt: str) -> str | None:
    value = input(f"{prompt} (Enter — пропустить): ").strip()
    return value or None


def _yes_no(prompt: str, *, default: bool = True) -> bool:
    marker = "Д/н" if default else "д/Н"
    value = input(f"{prompt} [{marker}]: ").strip().lower()
    if not value:
        return default
    return value in {"д", "да", "y", "yes", "1"}


def _source_args() -> list[str]:
    source_type = _choice(
        "Откуда брать Excel-файлы?",
        (
            ("1", "ZIP-архив"),
            ("2", "Папка с файлами"),
            ("3", "Один или несколько Excel-файлов"),
        ),
    )
    if source_type == "1":
        return ["--archive", _path("Перетащите ZIP в терминал", must_exist=True)]
    if source_type == "2":
        return ["--input-dir", _path("Перетащите папку в терминал", must_exist=True)]
    print("Перетащите файлы в терминал. Несколько путей можно разделить символом ;")
    while True:
        raw = input("Excel-файлы: ").strip()
        values = [_clean_dragged_path(item) for item in raw.split(";") if item.strip()]
        if values and all(Path(item).expanduser().is_file() for item in values):
            return ["--inputs", *values]
        print(_paint("Не удалось найти все указанные файлы.", _Color.RED))


def _common_args() -> list[str]:
    args: list[str] = []
    period = _optional("Период YYYY-MM, например 2026-07")
    if period:
        args.extend(["--period", period])
    args.extend(["--rag-mode", "off"])
    args.append("--strict" if _yes_no("Строгая проверка", default=True) else "--no-strict")
    args.extend(["--work-dir", "work"])
    return args


def _run_and_pause(cli_main: CliMain, argv: list[str]) -> None:
    print("\n" + _paint("Запуск проверки…", _Color.BLUE, _Color.BOLD))
    code = cli_main(argv)
    if code == 0:
        print(_paint("\nОперация завершена.", _Color.GREEN, _Color.BOLD))
    else:
        print(
            _paint(
                f"\nОперация завершилась со статусом {code}. Смотрите предупреждения выше.",
                _Color.RED,
            )
        )
    input("\nНажмите Enter, чтобы вернуться в меню…")


def _update_policy() -> str:
    choice = _choice(
        "Как обновлять существующие значения?",
        (
            ("1", "Заполнять только пустые ячейки — рекомендуется"),
            ("2", "Перезаписывать найденными значениями"),
            ("3", "Всегда сохранять существующие значения"),
            ("4", "Все конфликты направлять на ручную проверку"),
        ),
    )
    return {
        "1": "fill_empty_only",
        "2": "overwrite",
        "3": "keep_existing",
        "4": "conflicts_to_review",
    }[choice]


def _build(cli_main: CliMain, *, dry_run: bool, update: bool = False) -> None:
    args = ["build-drawing-card", *_source_args()]
    args.extend(_common_args())
    if update:
        existing = _path("Перетащите существующую карточку", must_exist=True)
        args.extend(
            [
                "--existing-card",
                existing,
                "--mode",
                "update",
                "--update-policy",
                _update_policy(),
            ]
        )
    else:
        template = _path(
            "Шаблон карточки",
            default="templates/default_drawing_card_template.xlsx",
            must_exist=True,
        )
        args.extend(["--template", template, "--mode", "create"])
    review_decisions = _optional("JSON с решениями ручной проверки (после импорта)")
    if review_decisions:
        args.extend(["--review-decisions", review_decisions])
    if dry_run:
        args.append("--dry-run")
    else:
        args.append("--interactive-review")
        default_output = (
            "output/карточка_остатков_обновленная.xlsx"
            if update
            else "output/карточка_остатков.xlsx"
        )
        output = _xlsx_output_path(
            "Куда сохранить карточку",
            default=default_output,
            default_filename=Path(default_output).name,
        )
        args.extend(["--output", output])
    _run_and_pause(cli_main, args)


def _inspect(cli_main: CliMain) -> None:
    output = _path("Куда сохранить отчёт", default="output/source_inspection.json")
    _run_and_pause(cli_main, ["inspect-drawing-sources", *_source_args(), "--output", output])


def _review(cli_main: CliMain) -> None:
    args = ["prepare-drawing-review", *_source_args(), *_common_args()]
    args.extend(["--template", "templates/default_drawing_card_template.xlsx"])
    _run_and_pause(cli_main, args)


def _validate(cli_main: CliMain) -> None:
    card = _path("Перетащите готовую карточку", must_exist=True)
    report = _path("Куда сохранить проверку", default="output/card_validation.json")
    _run_and_pause(cli_main, ["validate-drawing-card", "--card", card, "--output", report])


def _apply_review(cli_main: CliMain) -> None:
    review = _path("Перетащите заполненный manual_review.xlsx", must_exist=True)
    output = _path(
        "Куда сохранить решения",
        default="output/review_decisions.json",
    )
    args = ["apply-drawing-review", "--review", review, "--output", output]
    if _yes_no("Добавить явно подтвержденные строки в словарь примеров", default=False):
        args.extend(["--update-examples", "--confirmed-by", "manual-user"])
    _run_and_pause(cli_main, args)


def run(cli_main: CliMain) -> int:
    while True:
        _clear()
        _banner()
        action = _choice(
            "Главное меню",
            (
                ("1", "Создать итоговую карточку"),
                ("2", "Дополнить существующую карточку"),
                ("3", "Безопасный dry-run без записи карточки"),
                ("4", "Проверить и описать источники"),
                ("5", "Подготовить файл ручной проверки"),
                ("6", "Импортировать заполненную ручную проверку"),
                ("7", "Проверить готовую карточку"),
                ("0", "Выход"),
            ),
        )
        if action == "0":
            print("Работа завершена.")
            return 0
        if action == "1":
            _build(cli_main, dry_run=False)
        elif action == "2":
            _build(cli_main, dry_run=False, update=True)
        elif action == "3":
            _build(cli_main, dry_run=True)
        elif action == "4":
            _inspect(cli_main)
        elif action == "5":
            _review(cli_main)
        elif action == "6":
            _apply_review(cli_main)
        elif action == "7":
            _validate(cli_main)
