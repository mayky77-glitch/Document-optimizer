from pathlib import Path

import pytest

from report_processor.package_reconciliation import discover_document_packages


def test_discovers_workbooks_and_related_pdfs_without_nested_package_files(tmp_path: Path) -> None:
    (tmp_path / "root.xlsx").touch()
    (tmp_path / "root.pdf").touch()
    (tmp_path / "ordinary").mkdir()
    (tmp_path / "ordinary" / "evidence.PDF").touch()
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "child.xlsm").touch()
    (tmp_path / "nested" / "calc.ods").touch()
    (tmp_path / "nested" / "child.pdf").touch()

    discovery = discover_document_packages(tmp_path)

    assert tuple(item.relative_root.as_posix() for item in discovery.packages) == (".", "nested")
    root, nested = discovery.packages
    assert tuple(path.as_posix() for path in root.workbook_paths) == ("root.xlsx",)
    assert tuple(path.as_posix() for path in root.pdf_paths) == (
        "ordinary/evidence.PDF",
        "root.pdf",
    )
    assert tuple(path.as_posix() for path in nested.workbook_paths) == (
        "nested/calc.ods",
        "nested/child.xlsm",
    )
    assert tuple(path.as_posix() for path in nested.pdf_paths) == ("nested/child.pdf",)


def test_rejects_symlinked_supported_input(tmp_path: Path) -> None:
    workbook = tmp_path / "book.xlsx"
    workbook.touch()
    (tmp_path / "outside.pdf").touch()
    linked = tmp_path / "linked.pdf"
    linked.symlink_to(tmp_path / "outside.pdf")

    with pytest.raises(ValueError, match="symlinked input"):
        discover_document_packages(tmp_path)


def test_rejects_symlinked_root(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    link = tmp_path / "link"
    link.symlink_to(source, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinked package root"):
        discover_document_packages(link)


def test_rejects_encountered_symlinked_directory(tmp_path: Path) -> None:
    (tmp_path / "book.xlsx").touch()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinked directory"):
        discover_document_packages(tmp_path)
