"""CLI adapter for the loopback-only local administration panel."""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

import uvicorn

LOOPBACK_HOST = "127.0.0.1"


def add_admin_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "admin",
        help="Открыть локальную панель обработки отчётов",
    )
    parser.add_argument("--host", default=LOOPBACK_HOST, choices=(LOOPBACK_HOST, "localhost"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--workspace-directory", type=Path)
    parser.add_argument(
        "--open-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Открыть панель в браузере автоматически",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
    )


def run_admin(args: argparse.Namespace) -> int:
    if not 1 <= args.port <= 65_535:
        raise ValueError("Порт должен быть в диапазоне 1–65535")

    from report_processor.admin_panel import create_app

    app = create_app(workspace_root=args.workspace_directory)
    url = f"http://{LOOPBACK_HOST if args.host == 'localhost' else args.host}:{args.port}"
    if args.open_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.casefold(),
    )
    return 0
