from __future__ import annotations

from decimal import Decimal

import pytest

from report_processor.adapters import KS2Adapter, KS6AAdapter, SVVRAdapter, get_source_adapter
from report_processor.extraction import make_row_id, validate_canonical_source_row
from report_processor.extraction.exceptions import AdapterNotAvailableError
from report_processor.extraction.models import CanonicalSourceRow, SourceLocation
from report_processor.schema import SheetType


def test_registry_uses_separate_adapters():
    assert isinstance(get_source_adapter(SheetType.KS2), KS2Adapter)
    assert isinstance(get_source_adapter(SheetType.KS6A), KS6AAdapter)
    assert isinstance(get_source_adapter(SheetType.SVVR), SVVRAdapter)
    with pytest.raises(AdapterNotAvailableError, match="ADAPTER_NOT_AVAILABLE"):
        get_source_adapter(SheetType.KS3)


def test_row_id_is_deterministic_and_sheet_sensitive():
    first = make_row_id("file", "КС-2", 10)
    assert first == make_row_id("file", "КС-2", 10)
    assert first != make_row_id("file", "КС-6а", 10)
    assert first != make_row_id("file", "КС-2", 11)


def test_validation_rejects_non_finite_or_non_decimal_numeric():
    location = SourceLocation("file", "book.xlsx", "КС-2", "ks2", 2)
    row = CanonicalSourceRow(
        row_id="id",
        source_type="ks2",
        source_location=location,
        document_index=None,
        document_period=None,
        object_code_raw=None,
        object_name_raw=None,
        subobject_code_raw=None,
        subobject_name_raw=None,
        position_code_raw=None,
        work_name_raw="Работа",
        unit_raw=None,
        contract_quantity=None,
        current_period_quantity=Decimal("NaN"),
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=None,
        contract_cost=None,
        current_period_cost=None,
        cumulative_cost=None,
        total_cost=None,
        basis_code_raw=None,
        drawing_code_raw=None,
        cost_type_code_raw=None,
        source_values=(),
        status="OK",
        warnings=(),
    )
    issues = validate_canonical_source_row(row)
    assert any(issue.code == "NUMERIC_VALUE_INVALID" for issue in issues)


def test_row_id_matches_specified_sha256_payload():
    import hashlib

    parts = ("file", "КС-2", "10")
    payload = b"".join(
        len(part.encode("utf-8")).to_bytes(8, byteorder="big") + part.encode("utf-8")
        for part in parts
    )
    expected = hashlib.sha256(payload).hexdigest()
    assert make_row_id("file", "КС-2", 10) == expected


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (("file", "Sheet1", 23), ("file", "Sheet12", 3)),
        (("file", "A1", 11), ("file", "A11", 1)),
    ],
)
def test_row_id_framing_prevents_concatenation_collisions(
    first: tuple[str, str, int],
    second: tuple[str, str, int],
):
    assert make_row_id(*first) != make_row_id(*second)
