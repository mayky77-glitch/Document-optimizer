import zipfile
from pathlib import Path

from report_processor.drawing_card.sources.manifest import scan_archive
from report_processor.drawing_card.statuses import Status


def test_zip_manifest_ignores_service_entries_and_flags_zip_slip(tmp_path: Path) -> None:
    archive_path = tmp_path / "inputs.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("0906/good.xlsx", b"fake")
        archive.writestr("__MACOSX/._bad.xlsx", b"fake")
        archive.writestr("0906/~$temp.xlsx", b"fake")
        archive.writestr("../../unsafe.xlsx", b"fake")
        archive.writestr("manual.pdf", b"fake")
    entries = scan_archive(archive_path)
    assert [entry.logical_path for entry in entries] == ["0906/good.xlsx", "../../unsafe.xlsx"]
    unsafe = next(item for item in entries if item.logical_path == "../../unsafe.xlsx")
    assert Status.UNSAFE_ARCHIVE_PATH in unsafe.warnings
