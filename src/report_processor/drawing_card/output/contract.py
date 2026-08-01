"""Stable public layout contract for drawing-card XLSX output."""

CARD_HEADERS = (
    "Шифр чертежа",
    "Наименование этапа работ",
    "Ед. изм.",
    "Количество",
    "Общая стоимость",
)
INTEGER_QUANTITY_FORMAT = "0"
FRACTIONAL_QUANTITY_FORMAT = "0.###"
COST_FORMAT = "#,##0.000"
SUMMARY_SHEET_NAME = "Сводный отчет"
MAIN_CARD_SHEET_NAME = "Карточка остатков"
SUMMARY_HEADERS = (
    "Наименование этапа работ",
    "Ед. изм.",
    "Количество",
    "Общая стоимость",
)
SUMMARY_BLOCKS_PER_ROW = 2
SUMMARY_BLOCK_COLUMN_SPAN = 6
SUMMARY_BLOCK_ROW_SPAN = 11
