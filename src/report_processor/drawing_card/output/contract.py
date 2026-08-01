"""Stable public layout contract for drawing-card XLSX output."""

from decimal import Decimal

CARD_HEADERS = (
    "Шифр чертежа",
    "Наименование этапа работ",
    "Ед. изм.",
    "Количество",
    "Общая стоимость, млн руб.",
)
# Use display formats only: numeric cell values retain their full precision.
# Both quantity variants deliberately use the same format so every published
# value is rendered with exactly two fractional digits.
INTEGER_QUANTITY_FORMAT = "0.00"
FRACTIONAL_QUANTITY_FORMAT = "0.00"
COST_FORMAT = "#,##0.00"
DISPLAY_COST_SCALE = Decimal("1000000")
SUMMARY_SHEET_NAME = "Сводный отчет"
MAIN_CARD_SHEET_NAME = "Карточка остатков"
SUMMARY_HEADERS = (
    "Наименование этапа работ",
    "Ед. изм.",
    "Количество",
    "Общая стоимость, млн руб.",
)
SUMMARY_BLOCKS_PER_ROW = 2
SUMMARY_BLOCK_COLUMN_SPAN = 6
SUMMARY_BLOCK_ROW_SPAN = 11


def cost_to_million_rubles(value: Decimal | None, cost_scale: int) -> Decimal | None:
    """Convert an internal ruble cost to the published million-ruble amount."""

    if value is None:
        return None
    return value / Decimal(cost_scale) / DISPLAY_COST_SCALE
