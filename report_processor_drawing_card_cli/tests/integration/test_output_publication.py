from dataclasses import replace
from pathlib import Path

from openpyxl import load_workbook

from report_processor.drawing_card.models import WorkflowRequest
from report_processor.drawing_card.workflow import run_workflow


def test_output_publication_records_a_matching_strategy(project_root: Path, tmp_path: Path) -> None:
    output = tmp_path / "result.xlsx"
    result = run_workflow(
        WorkflowRequest(
            inputs=(project_root / "examples" / "0906_demo_input.xlsx",),
            template=project_root / "templates" / "default_drawing_card_template.xlsx",
            output=output,
            mode="create",
            rag_mode="off",
            strict=True,
            work_dir=tmp_path / "work",
        )
    )

    assert result.status == "OK"
    assert result.write_operations
    assert all(operation.matching_strategy for operation in result.write_operations)
    assert all(
        operation.matching_strategy != "output_writer" for operation in result.write_operations
    )
    assert all(operation.matching_strategies for operation in result.write_operations)


def test_dry_run_operations_match_actual_writer_audit(project_root: Path, tmp_path: Path) -> None:
    request = dict(
        inputs=(project_root / "examples" / "0906_demo_input.xlsx",),
        template=project_root / "templates" / "default_drawing_card_template.xlsx",
        mode="create",
        rag_mode="off",
        strict=True,
    )
    dry_result = run_workflow(
        WorkflowRequest(**request, dry_run=True, work_dir=tmp_path / "dry-work")
    )
    actual_result = run_workflow(
        WorkflowRequest(
            **request,
            output=tmp_path / "result.xlsx",
            work_dir=tmp_path / "actual-work",
        )
    )

    assert dry_result.status == "OK"
    assert actual_result.status == "OK"
    assert dry_result.write_operations
    assert dry_result.write_operations == [
        replace(operation, old_value=None, run_id=dry_result.run_id)
        for operation in actual_result.write_operations
    ]


def test_update_operations_record_original_metric_values(
    project_root: Path, tmp_path: Path
) -> None:
    existing_card = tmp_path / "existing.xlsx"
    created = run_workflow(
        WorkflowRequest(
            inputs=(project_root / "examples" / "0906_demo_input.xlsx",),
            template=project_root / "templates" / "default_drawing_card_template.xlsx",
            output=existing_card,
            mode="create",
            rag_mode="off",
            strict=True,
            work_dir=tmp_path / "create-work",
        )
    )
    workbook = load_workbook(existing_card)
    try:
        original_values = {
            (operation.output_sheet, operation.output_cell): workbook[operation.output_sheet][
                operation.output_cell
            ].value
            for operation in created.write_operations
        }
    finally:
        workbook.close()
    updated = run_workflow(
        WorkflowRequest(
            inputs=(project_root / "examples" / "0906_demo_input.xlsx",),
            existing_card=existing_card,
            output=tmp_path / "updated.xlsx",
            mode="update",
            rag_mode="off",
            strict=True,
            work_dir=tmp_path / "update-work",
        )
    )

    assert created.status == "OK"
    assert updated.status == "OK"
    assert updated.write_operations
    assert all(
        operation.old_value == original_values[(operation.output_sheet, operation.output_cell)]
        for operation in updated.write_operations
    )
    assert any(
        operation.old_value == operation.new_value == "шт" for operation in updated.write_operations
    )
