"""CLI adapter for offline Excel/PDF package reconciliation."""

from __future__ import annotations

import argparse
import logging

from .package_reconciliation.pipeline import reconcile_package
from .package_reconciliation.report import write_report_atomically


def add_package_reconciliation_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "reconcile-package", help="Сверить строки Excel с АОСР из той же папки пакета"
    )
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), default="INFO"
    )


def run_package_reconciliation(args: argparse.Namespace) -> int:
    try:
        report = reconcile_package(args.package)
        write_report_atomically(report, args.output)
    except (OSError, ValueError) as error:
        logging.error("Не удалось выполнить сверку пакета: %s", type(error).__name__)
        return 2
    return 0
