from __future__ import annotations

from report_processor.extraction.exceptions import AdapterNotAvailableError
from report_processor.schema import SheetType

from .base import SourceAdapter
from .ks2 import KS2Adapter
from .ks6a import KS6AAdapter
from .svvr import SVVRAdapter

_ADAPTER_FACTORIES = {
    SheetType.KS2: KS2Adapter,
    SheetType.KS6A: KS6AAdapter,
    SheetType.SVVR: SVVRAdapter,
}


def get_source_adapter(sheet_type: SheetType) -> SourceAdapter:
    try:
        return _ADAPTER_FACTORIES[sheet_type]()
    except KeyError as exc:
        raise AdapterNotAvailableError(f"ADAPTER_NOT_AVAILABLE:{sheet_type.value}") from exc
