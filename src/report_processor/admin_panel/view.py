"""Local, package-owned assets for the administrative panel."""

from __future__ import annotations

from pathlib import Path

_ASSET_DIRECTORY = Path(__file__).with_name("assets")
_PUBLIC_ASSETS = {
    "admin.css": ("text/css; charset=utf-8", _ASSET_DIRECTORY / "admin.css"),
    "admin.js": ("text/javascript; charset=utf-8", _ASSET_DIRECTORY / "admin.js"),
    "drawing-card.css": (
        "text/css; charset=utf-8",
        _ASSET_DIRECTORY / "drawing-card.css",
    ),
    "drawing-card.js": (
        "text/javascript; charset=utf-8",
        _ASSET_DIRECTORY / "drawing-card.js",
    ),
}


def index_page() -> str:
    """Return the packaged one-screen application shell."""

    return (_ASSET_DIRECTORY / "index.html").read_text(encoding="utf-8")


def drawing_card_page() -> str:
    """Return the separate drawing-card application shell."""

    return (_ASSET_DIRECTORY / "drawing-card.html").read_text(encoding="utf-8")


def static_asset(path: str) -> tuple[str, bytes]:
    """Return one explicitly published local asset."""

    try:
        media_type, asset_path = _PUBLIC_ASSETS[path]
    except KeyError as error:
        raise KeyError("unknown static asset") from error
    return media_type, asset_path.read_bytes()
