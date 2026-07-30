from report_processor.materialization.safety import is_unsafe_archive_path, safe_local_filename


def test_zip_slip_and_absolute_paths_are_rejected():
    unsafe = [
        "../../file.xlsx",
        "/absolute/file.xlsx",
        r"C:\absolute\file.xlsx",
        r"\\server\share\file.xlsx",
        "folder/../file.xlsx",
    ]
    assert all(is_unsafe_archive_path(value) for value in unsafe)
    assert not is_unsafe_archive_path("folder/sub/file.xlsx")


def test_safe_local_filename_removes_reserved_and_separators():
    name = safe_local_filename("a91c2e10ff", r"folder\CON.xlsx", ".xlsx")
    assert name.startswith("a91c2e10_")
    assert name.endswith(".xlsx")
    assert "/" not in name and "\\" not in name and ":" not in name
    assert len(name) <= 120
