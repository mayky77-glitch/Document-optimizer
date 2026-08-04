"""Safe, deterministic discovery of package roots and related PDFs."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from .models import DocumentPackage, PackageDiscovery

_WORKBOOK_EXTENSIONS = {".xlsx", ".xlsm"}
_PDF_EXTENSION = ".pdf"


def _ensure_safe_root(root: Path) -> Path:
    if root.is_symlink():
        raise ValueError("symlinked package root is not allowed")
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("package discovery root must be a directory")
    return resolved


def _relative(root: Path, path: Path) -> PurePosixPath:
    if path.is_symlink():
        raise ValueError(f"symlinked input is not allowed: {path.name}")
    resolved = path.resolve(strict=True)
    try:
        return PurePosixPath(resolved.relative_to(root).as_posix())
    except ValueError as error:
        raise ValueError("input path escapes the discovery root") from error


def _direct_workbooks(directory: Path, source_root: Path) -> tuple[PurePosixPath, ...]:
    result: list[PurePosixPath] = []
    for child in sorted(directory.iterdir(), key=lambda value: value.name.casefold()):
        if child.is_symlink():
            if child.suffix.lower() in _WORKBOOK_EXTENSIONS | {_PDF_EXTENSION}:
                _relative(source_root, child)
            continue
        if child.is_file() and child.suffix.lower() in _WORKBOOK_EXTENSIONS:
            result.append(_relative(source_root, child))
    return tuple(sorted(result))


def _collect_pdfs(
    package_root: Path,
    source_root: Path,
    nested_roots: set[Path],
) -> tuple[PurePosixPath, ...]:
    found: list[PurePosixPath] = []
    stack = [package_root]
    while stack:
        directory = stack.pop()
        children = sorted(
            directory.iterdir(), key=lambda value: value.name.casefold(), reverse=True
        )
        for child in children:
            if child.is_symlink():
                if child.suffix.lower() in _WORKBOOK_EXTENSIONS | {_PDF_EXTENSION}:
                    _relative(source_root, child)
                continue
            if child.is_dir():
                if child != package_root and child in nested_roots:
                    continue
                stack.append(child)
            elif child.is_file() and child.suffix.lower() == _PDF_EXTENSION:
                found.append(_relative(source_root, child))
    return tuple(sorted(found))


def discover_document_packages(source_root: Path) -> PackageDiscovery:
    """Find package directories without allowing a child package to leak upward."""

    root = _ensure_safe_root(Path(source_root))
    candidates: list[Path] = []
    for directory, directories, _files in os.walk(root, followlinks=False):
        path = Path(directory)
        for name in tuple(directories):
            child = path / name
            if child.is_symlink():
                raise ValueError(f"symlinked directory is not allowed: {child.name}")
        if _direct_workbooks(path, root):
            candidates.append(path)

    package_roots = set(candidates)
    packages: list[DocumentPackage] = []
    for package_root in sorted(package_roots, key=lambda value: value.relative_to(root).as_posix()):
        packages.append(
            DocumentPackage(
                relative_root=PurePosixPath(package_root.relative_to(root).as_posix()),
                workbook_paths=_direct_workbooks(package_root, root),
                pdf_paths=_collect_pdfs(package_root, root, package_roots),
            )
        )
    return PackageDiscovery(packages=tuple(packages))
