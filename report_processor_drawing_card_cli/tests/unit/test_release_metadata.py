"""Release metadata consistency checks."""

from __future__ import annotations

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import report_processor

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_NAME = "report-processor"


def _project_version_from_lockfile() -> str:
    lockfile = tomllib.loads((PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
    package = next(item for item in lockfile["package"] if item["name"] == PROJECT_NAME)
    return package["version"]


def test_release_version_metadata_is_consistent() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared_version = pyproject["project"]["version"]

    assert report_processor.__version__ == declared_version
    assert _project_version_from_lockfile() == declared_version

    try:
        installed_version = version(PROJECT_NAME)
    except PackageNotFoundError:
        # Source-tree test runs do not require an editable/package installation.
        return

    assert installed_version == declared_version
