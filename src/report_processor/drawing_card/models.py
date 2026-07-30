"""Immutable domain models for drawing-card processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any


class TargetWorkCategory(StrEnum):
    PILE_FOUNDATION = "pile_foundation"
    CONCRETE_WORKS = "concrete_works"
    METAL_STRUCTURES = "metal_structures"
    TSG_DRIVING = "tsg_driving"
    TT_INSTALLATION = "tt_installation"
    TT_VALVES_INSTALLATION = "tt_valves_installation"
    POWER_CABLE = "power_cable"
    LOW_CURRENT_CABLE = "low_current_cable"


CATEGORY_DISPLAY_NAMES: dict[TargetWorkCategory, str] = {
    TargetWorkCategory.PILE_FOUNDATION: "Устройство свайного основания",
    TargetWorkCategory.CONCRETE_WORKS: "Бетонные работы",
    TargetWorkCategory.METAL_STRUCTURES: "Монтаж металлоконструкций",
    TargetWorkCategory.TSG_DRIVING: "Погружение ТСГ",
    TargetWorkCategory.TT_INSTALLATION: "Монтаж ТТ",
    TargetWorkCategory.TT_VALVES_INSTALLATION: "Монтаж ЗРА ТТ",
    TargetWorkCategory.POWER_CABLE: "Прокладка кабеля, провода (Силовые сети)",
    TargetWorkCategory.LOW_CURRENT_CABLE: "Прокладка кабеля, провода (Слаботочные сети)",
}

CATEGORY_ORDER: tuple[TargetWorkCategory, ...] = tuple(TargetWorkCategory)


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    file_id: str
    source_kind: str
    container_path: str
    logical_path: str
    filename: str
    extension: str
    size: int
    compressed_size: int | None
    object_index_hint: str | None
    document_type: str | None
    period: str | None
    revision: str | None
    is_temporary: bool
    is_copy: bool
    is_outdated: bool
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ObjectIdentityResult:
    value: str | None
    source: str | None
    confidence: float
    candidates: tuple[str, ...]
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceSchema:
    sheet_name: str
    header_start_row: int
    header_end_row: int
    data_start_row: int
    columns: dict[str, int]
    logical_headers: dict[int, str]
    confidence: float
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DrawingSourceLocation:
    file_id: str
    filename: str
    sheet_name: str
    row_number: int
    coordinates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DrawingSourceRow:
    row_id: str
    location: DrawingSourceLocation
    object_index_raw: str | None
    drawing_code_raw: str | None
    work_name_raw: str | None
    unit_raw: str | None
    remaining_quantity: Decimal | None
    remaining_total_cost: Decimal | None
    formula_values: tuple[Any, ...]
    cached_values: tuple[Any, ...]
    source_document_type: str | None
    source_period: str | None
    source_revision: str | None
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DrawingCode:
    raw: str
    normalized: str
    group_key: str
    components: tuple[str, ...]
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MatchDecision:
    row_id: str
    category: TargetWorkCategory | None
    quantity_decision: str
    cost_decision: str
    quantity_rule_id: str | None
    cost_rule_id: str | None
    quantity_confidence: float | None
    cost_confidence: float | None
    matching_strategy: str
    evidence_ids: tuple[str, ...]
    reason: str
    requires_manual_review: bool
    status: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AggregatedDrawingResult:
    object_index: str
    drawing_code: DrawingCode
    category: TargetWorkCategory
    unit: str | None
    quantity: Decimal | None
    total_cost: Decimal | None
    quantity_rows: tuple[str, ...]
    cost_rows: tuple[str, ...]
    quantity_rule_id: str | None
    cost_rule_id: str | None
    quantity_confidence: float | None
    cost_confidence: float | None
    status: str
    requires_manual_review: bool
    warnings: tuple[str, ...]
    quantity_matching_strategies: tuple[str, ...] = ()
    cost_matching_strategies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DrawingCardResultRow:
    object_index: str
    drawing_code: DrawingCode
    category: TargetWorkCategory
    display_name: str
    result_unit: str | None
    remaining_quantity: Decimal | None
    remaining_total_cost: Decimal | None
    quantity_source_rows: tuple[str, ...]
    cost_source_rows: tuple[str, ...]
    quantity_rule_id: str | None
    cost_rule_id: str | None
    quantity_confidence: float | None
    cost_confidence: float | None
    requires_manual_review: bool
    status: str
    warnings: tuple[str, ...]
    quantity_matching_strategies: tuple[str, ...] = ()
    cost_matching_strategies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DrawingCodeBlockLayout:
    drawing_code: str
    start_row: int
    end_row: int


@dataclass(frozen=True, slots=True)
class ObjectBlockLayout:
    sheet_name: str
    object_index: str
    start_column: int
    end_column: int
    header_row: int
    column_header_row: int
    data_start_row: int
    drawing_code_blocks: tuple[DrawingCodeBlockLayout, ...]


@dataclass(frozen=True, slots=True)
class WriteOperation:
    run_id: str
    output_sheet: str
    output_cell: str
    object_index: str
    drawing_code: str
    category: str
    metric: str
    old_value: Any
    new_value: Any
    unit: str | None
    source_rows: tuple[str, ...]
    rule_id: str | None
    matching_strategy: str | None
    confidence: float | None
    confirmation_status: str
    warnings: tuple[str, ...]
    matching_strategies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowRequest:
    inputs: tuple[Path, ...] = ()
    input_dir: Path | None = None
    archive: Path | None = None
    template: Path | None = None
    existing_card: Path | None = None
    output: Path | None = None
    mode: str = "create"
    period: str | None = None
    object_map: Path | None = None
    rules: Path | None = None
    examples: Path | None = None
    rag_mode: str = "off"
    model_config: Path | None = None
    review_decisions: Path | None = None
    objects_per_sheet: int = 4
    drawing_code_mode: str = "preserve_group"
    remaining_strategy: str = "direct_remaining_columns"
    update_policy: str = "fill_empty_only"
    strict: bool = True
    dry_run: bool = False
    work_dir: Path = Path("work")
    log_level: str = "INFO"


@dataclass(slots=True)
class WorkflowResult:
    run_id: str
    status: str
    work_dir: Path
    manifest: list[ManifestEntry] = field(default_factory=list)
    schemas: list[SourceSchema] = field(default_factory=list)
    source_rows: list[DrawingSourceRow] = field(default_factory=list)
    decisions: list[MatchDecision] = field(default_factory=list)
    extracted_row_count: int = 0
    classification_decision_count: int = 0
    manual_review_count: int = 0
    aggregated: list[AggregatedDrawingResult] = field(default_factory=list)
    card_rows: list[DrawingCardResultRow] = field(default_factory=list)
    layouts: list[ObjectBlockLayout] = field(default_factory=list)
    write_operations: list[WriteOperation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    output_path: Path | None = None
