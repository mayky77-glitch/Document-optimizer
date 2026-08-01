from types import SimpleNamespace

from report_processor.admin_panel.presentation import job_payload, processing_presentation


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


def test_manual_discrepancies_are_grouped_and_removed_from_passive_list() -> None:
    job = {
        "job_id": "job-1",
        "stage": "13.1",
        "status": "review_required",
        "summary": {"manual_review_issue_count": 492},
        "discrepancies": [
            {
                "discrepancy_id": f"issue-{index}",
                "code": "AMBIGUOUS",
                "category": "manual_review",
                "severity": "manual_review",
                "message": "Связь требует ручной проверки",
            }
            for index in range(492)
        ]
        + [
            {
                "discrepancy_id": "warning-1",
                "category": "unchanged_value",
                "message": "Без изменения",
            }
        ],
        "suggestions": [],
        "decisions": [],
        "download_url": None,
    }

    payload = job_payload(job)

    assert payload["summary"]["manual_review_issue_count"] == 492
    assert payload["suggestions"] == []
    assert len(payload["manual_review_groups"]) == 1
    assert payload["manual_review_groups"][0]["count"] == 492
    assert len(payload["manual_review_groups"][0]["discrepancy_ids"]) == 492
    assert payload["discrepancies"] == [
        {"discrepancy_id": "warning-1", "category": "unchanged_value", "message": "Без изменения"}
    ]


def test_repeated_passive_warnings_collapse_to_one_counted_row() -> None:
    job = {
        "job_id": "job-1",
        "stage": "13.1",
        "status": "ready",
        "summary": {},
        "discrepancies": [
            {
                "discrepancy_id": f"warning-{index}",
                "code": "UPSTREAM_WARNING",
                "category": "unchanged_value",
                "severity": "warning",
                "color": "yellow",
                "message": "Исходное значение представлено без изменения.",
            }
            for index in range(173)
        ],
        "suggestions": [],
        "decisions": [],
        "download_url": "/api/jobs/job-1/result",
    }

    payload = job_payload(job)

    assert payload["manual_review_groups"] == []
    assert payload["discrepancies"] == [
        {
            "discrepancy_id": "warning-0",
            "code": "UPSTREAM_WARNING",
            "category": "unchanged_value",
            "severity": "warning",
            "color": "yellow",
            "message": "Исходное значение представлено без изменения.",
            "count": 173,
        }
    ]
