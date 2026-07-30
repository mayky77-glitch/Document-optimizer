from types import SimpleNamespace

from report_processor.admin_panel.presentation import processing_presentation


def test_rag_candidates_are_separate_named_manual_decisions() -> None:
    normalized = SimpleNamespace(
        rows=(
            SimpleNamespace(
                source_row_id="source-pipe",
                work_name="Монтаж трубопровода",
                position_code=None,
            ),
            SimpleNamespace(
                source_row_id="source-concrete",
                work_name="Устройство бетонной подготовки",
                position_code=None,
            ),
        )
    )
    matches = (
        SimpleNamespace(
            result_id="target-stage",
            target_row=SimpleNamespace(stage="13.1. Подготовительные работы", work_name=None),
        ),
    )
    suggestion = SimpleNamespace(
        target_identity="target-stage",
        candidates=(
            SimpleNamespace(source_identity="source-pipe", score=0.91),
            SimpleNamespace(source_identity="source-concrete", score=0.82),
        ),
    )
    result = SimpleNamespace(
        artifacts={
            "normalized": normalized,
            "matches": matches,
            "stage_relation_suggestions": (suggestion,),
        },
        state="MANUAL_REVIEW_REQUIRED",
        exit_code=3,
        warnings=(),
        errors=(),
    )

    _, _, suggestions = processing_presentation(result)

    assert len(suggestions) == 2
    assert {item["candidate_label"] for item in suggestions} == {
        "Монтаж трубопровода",
        "Устройство бетонной подготовки",
    }
    assert {item["target_label"] for item in suggestions} == {"13.1. Подготовительные работы"}
    assert len({item["suggestion_id"] for item in suggestions}) == 2
    assert all(item["requires_manual_review"] is True for item in suggestions)
    assert all(item["auto_accepted"] is False for item in suggestions)
