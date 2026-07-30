"""JSON serialization through the existing atomic writer."""

from dataclasses import asdict
from pathlib import Path

from report_processor.report_serialization import save_inspection_report
from report_processor.schema.models import WorkbookSchema


def save_workbook_schema_json(schema: WorkbookSchema, output_path: Path) -> None:
    save_inspection_report(asdict(schema), output_path)
