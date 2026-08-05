"""Local, package-owned assets for the administrative panel."""

from __future__ import annotations

from pathlib import Path

_ASSET_DIRECTORY = Path(__file__).with_name("assets")
_PUBLIC_ASSETS = {
    "admin.css": ("text/css; charset=utf-8", _ASSET_DIRECTORY / "admin.css"),
    "admin.js": ("text/javascript; charset=utf-8", _ASSET_DIRECTORY / "admin.js"),
    "reconciliation-batches.js": (
        "text/javascript; charset=utf-8",
        _ASSET_DIRECTORY / "reconciliation-batches.js",
    ),
    "reconciliation-batch-filters.js": (
        "text/javascript; charset=utf-8",
        _ASSET_DIRECTORY / "reconciliation-batch-filters.js",
    ),
    "reconciliation-active-learning.js": (
        "text/javascript; charset=utf-8",
        _ASSET_DIRECTORY / "reconciliation-active-learning.js",
    ),
    "theme.js": ("text/javascript; charset=utf-8", _ASSET_DIRECTORY / "theme.js"),
    "drawing-card.css": (
        "text/css; charset=utf-8",
        _ASSET_DIRECTORY / "drawing-card.css",
    ),
    "drawing-card.js": (
        "text/javascript; charset=utf-8",
        _ASSET_DIRECTORY / "drawing-card.js",
    ),
    "drawing-card-review.js": (
        "text/javascript; charset=utf-8",
        _ASSET_DIRECTORY / "drawing-card-review.js",
    ),
    "package-reconciliation.css": (
        "text/css; charset=utf-8",
        _ASSET_DIRECTORY / "package-reconciliation.css",
    ),
    "package-reconciliation.js": (
        "text/javascript; charset=utf-8",
        _ASSET_DIRECTORY / "package-reconciliation.js",
    ),
    "help.css": ("text/css; charset=utf-8", _ASSET_DIRECTORY / "help.css"),
}


def index_page() -> str:
    """Return the packaged one-screen application shell."""

    return (_ASSET_DIRECTORY / "index.html").read_text(encoding="utf-8")


def drawing_card_page() -> str:
    """Return the separate drawing-card application shell."""

    return (_ASSET_DIRECTORY / "drawing-card.html").read_text(encoding="utf-8")


def package_reconciliation_page() -> str:
    """Return the package reconciliation workflow shell."""

    return (_ASSET_DIRECTORY / "package-reconciliation.html").read_text(encoding="utf-8")


def help_page() -> str:
    """Return the local workflow guide shell."""

    return (_ASSET_DIRECTORY / "help.html").read_text(encoding="utf-8")


def static_asset(path: str) -> tuple[str, bytes]:
    """Return one explicitly published local asset."""

    try:
        media_type, asset_path = _PUBLIC_ASSETS[path]
    except KeyError as error:
        raise KeyError("unknown static asset") from error
    return media_type, asset_path.read_bytes()
