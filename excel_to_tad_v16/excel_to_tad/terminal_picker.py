"""Кроссплатформенный интерактивный выбор путей в терминале."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from .constants import SUPPORTED_EXTENSIONS


class SelectionCancelled(Exception):
    """Пользователь отменил интерактивный выбор пути."""


def _default_start_directory() -> Path:
    """Возвращает удобную стартовую папку, доступную на всех ОС."""
    current = Path.cwd()
    try:
        if current.is_dir() and any(
            item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
            for item in current.iterdir()
        ):
            return current.resolve()
    except OSError:
        pass

    candidates = (
        Path.home() / "Documents",
        Path.home(),
        current,
    )
    for candidate in candidates:
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            continue
    return Path.cwd().absolute()


def _safe_resolve(path: Path) -> Path:
    """Разрешает путь без падения на недоступных сетевых каталогах."""
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser().absolute()


def _sorted_directories(directory: Path) -> list[Path]:
    try:
        entries = list(directory.iterdir())
    except (OSError, PermissionError) as exc:
        print(f"Не удалось открыть каталог: {exc}", file=sys.stderr)
        return []

    return sorted(
        (
            entry
            for entry in entries
            if entry.is_dir() and not entry.name.startswith(".")
        ),
        key=lambda item: item.name.casefold(),
    )


def _sorted_excel_files(directory: Path) -> list[Path]:
    try:
        entries = list(directory.iterdir())
    except (OSError, PermissionError) as exc:
        print(f"Не удалось открыть каталог: {exc}", file=sys.stderr)
        return []

    return sorted(
        (
            entry
            for entry in entries
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda item: item.name.casefold(),
    )


def _path_from_user_input(value: str) -> Path:
    """Очищает вставленный путь от кавычек и экранирования пробелов."""
    cleaned = value.strip()
    if (
        len(cleaned) >= 2
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {"\"", "'"}
    ):
        cleaned = cleaned[1:-1]
    if os.name != "nt":
        cleaned = cleaned.replace("\\ ", " ")
    return Path(cleaned)


def _resolve_user_path(value: str, current: Path) -> Path:
    """Разрешает абсолютный либо относительный к текущему каталогу путь."""
    candidate = _path_from_user_input(value)
    if not candidate.is_absolute():
        candidate = current / candidate
    return _safe_resolve(candidate)


def _print_items(
    directory: Path,
    directories: Sequence[Path],
    files: Sequence[Path] = (),
    *,
    directory_mode: bool,
) -> list[Path]:
    """Печатает содержимое каталога и возвращает индексируемые элементы."""
    print("\n" + "=" * 72)
    print(f"Текущая папка: {directory}")
    print("=" * 72)

    indexed_items: list[Path] = []
    for item in directories:
        indexed_items.append(item)
        print(f"[{len(indexed_items):>3}] [DIR] {item.name}/")

    for item in files:
        indexed_items.append(item)
        print(f"[{len(indexed_items):>3}] [XLS] {item.name}")

    if not indexed_items:
        print("  В этой папке подходящих элементов нет.")

    print("\nКоманды:")
    if directory_mode:
        print("  Enter или .  — выбрать текущую папку")
    print("  номер         — открыть папку или выбрать файл")
    print("  ..            — перейти на уровень выше")
    print("  ~             — перейти в домашнюю папку")
    print("  полный путь   — открыть или выбрать указанный путь")
    print("  q             — отменить")
    return indexed_items


def _read_choice(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise SelectionCancelled("Выбор отменён.") from exc


def choose_excel_file(start_directory: Path | None = None) -> Path:
    """Позволяет выбрать Excel-файл, перемещаясь по каталогам терминала."""
    current = _safe_resolve(start_directory or _default_start_directory())
    if current.is_file():
        current = current.parent

    while True:
        directories = _sorted_directories(current)
        files = _sorted_excel_files(current)
        items = _print_items(
            current,
            directories,
            files,
            directory_mode=False,
        )
        choice = _read_choice("Выберите Excel-файл: ")

        if choice.casefold() in {"q", "quit", "exit", "выход"}:
            raise SelectionCancelled("Выбор Excel-файла отменён.")
        if choice == "..":
            current = current.parent
            continue
        if choice == "~":
            current = _safe_resolve(Path.home())
            continue
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(items):
                selected = items[index]
                if selected.is_dir():
                    current = _safe_resolve(selected)
                else:
                    return _safe_resolve(selected)
            else:
                print("Нет элемента с таким номером.", file=sys.stderr)
            continue

        if choice:
            candidate = _resolve_user_path(choice, current)
            if candidate.is_dir():
                current = candidate
                continue
            if candidate.is_file():
                if candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    return candidate
                print(
                    "Поддерживаются только файлы .xlsx, .xlsm и .xlsb.",
                    file=sys.stderr,
                )
                continue
            print("Указанный путь не найден.", file=sys.stderr)
            continue

        print("Введите номер файла, путь или команду q.", file=sys.stderr)


def choose_output_directory(start_directory: Path | None = None) -> Path:
    """Позволяет выбрать существующую папку результата в терминале."""
    current = _safe_resolve(start_directory or _default_start_directory())
    if current.is_file():
        current = current.parent

    while True:
        directories = _sorted_directories(current)
        items = _print_items(
            current,
            directories,
            directory_mode=True,
        )
        choice = _read_choice("Выберите папку результата: ")

        if choice.casefold() in {"q", "quit", "exit", "выход"}:
            raise SelectionCancelled("Выбор папки результата отменён.")
        if choice in {"", "."}:
            return current
        if choice == "..":
            current = current.parent
            continue
        if choice == "~":
            current = _safe_resolve(Path.home())
            continue
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(items):
                current = _safe_resolve(items[index])
            else:
                print("Нет папки с таким номером.", file=sys.stderr)
            continue

        candidate = _resolve_user_path(choice, current)
        if candidate.is_dir():
            current = candidate
            continue
        print("Папка не найдена.", file=sys.stderr)


def _interactive_terminal_available() -> bool:
    """Проверяет, можно ли безопасно запрашивать ввод пользователя."""
    return bool(sys.stdin and sys.stdin.isatty())


def resolve_paths_interactively(args: argparse.Namespace) -> argparse.Namespace:
    """Заполняет отсутствующие пути с помощью терминального навигатора."""
    force_interactive = bool(
        getattr(args, "interactive", False) or getattr(args, "gui", False)
    )
    needs_input = force_interactive or not getattr(args, "input_file", None)
    needs_output = force_interactive or not getattr(args, "output_directory", None)

    args.interactive_used = bool(needs_input or needs_output)
    if not args.interactive_used:
        return args

    if not _interactive_terminal_available():
        raise RuntimeError(
            "Интерактивный выбор требует терминала. Передайте пути аргументами: "
            "excel_to_tad.py <файл.xlsx> <папка_результата>."
        )

    selected_input = getattr(args, "input_file", None)
    if needs_input:
        selected_input = choose_excel_file()

    selected_input_path = _safe_resolve(Path(str(selected_input)))
    if needs_output:
        selected_output = choose_output_directory(selected_input_path.parent)
    else:
        selected_output = _safe_resolve(Path(str(args.output_directory)))

    args.input_file = str(selected_input_path)
    args.output_directory = str(selected_output)
    return args
