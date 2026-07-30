import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from report_processor.cli import main
from report_processor.drawing_card.review.io import import_review_approvals


@pytest.mark.parametrize(
    ("action", "category"),
    [
        ("approve", "concrete_works"),
        ("reject", None),
        ("skip", None),
    ],
)
def test_apply_review_json_is_loadable_by_workflow_option(
    action: str, category: str | None, project_root: Path, tmp_path: Path
) -> None:
    source = project_root / "examples" / "0906_demo_input.xlsx"
    template = project_root / "templates" / "default_drawing_card_template.xlsx"
    work_dir = tmp_path / "work"
    decisions = tmp_path / "review_decisions.json"
    assert (
        main(
            [
                "prepare-drawing-review",
                "--inputs",
                str(source),
                "--template",
                str(template),
                "--rag-mode",
                "off",
                "--work-dir",
                str(work_dir),
            ]
        )
        == 0
    )
    run_dir = next(work_dir.iterdir())
    review = run_dir / "manual_review.xlsx"
    row_id = json.loads((run_dir / "extracted_rows.jsonl").read_text().splitlines()[0])["row_id"]
    workbook = load_workbook(review)
    try:
        values = [None] * 18
        values[0] = row_id
        values[10] = category
        values[16] = action
        workbook["Review"].append(values)
        workbook.save(review)
    finally:
        workbook.close()

    assert main(["apply-drawing-review", "--review", str(review), "--output", str(decisions)]) == 0
    payload = json.loads(decisions.read_text(encoding="utf-8"))
    assert payload[row_id]["action"] == action
    assert import_review_approvals(decisions)[row_id].action == action
    output = tmp_path / f"{action}.xlsx"
    assert (
        main(
            [
                "build-drawing-card",
                "--inputs",
                str(source),
                "--template",
                str(template),
                "--output",
                str(output),
                "--review-decisions",
                str(decisions),
                "--rag-mode",
                "off",
                "--work-dir",
                str(tmp_path / "build-work"),
            ]
        )
        == 0
    )
    assert output.exists()
