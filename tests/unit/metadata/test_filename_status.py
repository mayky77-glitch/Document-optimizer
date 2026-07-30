from report_processor.metadata.filename_status import extract_filename_status


def test_filename_status_combines_independent_flags() -> None:
    status = extract_filename_status("~$1006 КС-6а ред2 черновик (1) неактуал.xlsx")
    assert status.is_temporary
    assert status.is_probable_copy
    assert status.is_probably_outdated
    assert status.is_draft
    assert status.revision_result.value.number == 2
