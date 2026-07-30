"""Запуск пакета: python -m excel_to_tad."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from .cli import parse_args
from .converter import convert
from .manifest import CONVERTER_VERSION
from .terminal_picker import SelectionCancelled, resolve_paths_interactively


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"Excel → Parquet/Tad — версия {CONVERTER_VERSION}")

    try:
        args = resolve_paths_interactively(args)
        result_directory = convert(args)
        if getattr(args, "interactive_used", False):
            print(f"\nГотово. Результат сохранён в папке:\n{result_directory}")
        return 0
    except SelectionCancelled as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 0
    except KeyboardInterrupt:
        print("\nОперация отменена.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI boundary reports unexpected failures.
        message = f"{type(exc).__name__}: {exc}"
        print(f"\nОшибка: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
