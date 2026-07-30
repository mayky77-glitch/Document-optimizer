"""Excel → Parquet/Tad converter package."""

from .converter import convert
from .manifest import CONVERTER_VERSION

__all__ = ["CONVERTER_VERSION", "convert"]
