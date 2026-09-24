"""Tests for the canonical historical-panel join."""

from datetime import UTC, datetime

from scripts.build_historical_panel import build_rows

from valtide_api.adapters.equity import RawEquityBar
from valtide_api.adapters.okx import RawCandle
from valtide_api.adapters.reference import RawReferenceCandle


def test_panel_builder_preserves_grid_and_does_not_fill_token_or_reference():
    start = datetime(2026, 9, 22, 14, 0, tzinfo=UTC)
    end = datetime(2026, 9, 22, 14, 10, tzinfo=UTC)
    token = [
        RawCandle(start, 180, 181, 179, 180.1, 500, 90_000, 1),
        RawCandle(end, 180.2, 181.2, 179.2, 180.3, 700, 126_000, 1),
    ]
    underlying = [RawEquityBar(start, 180, 181, 179, 180.0, 1000)]
    reference = [RawReferenceCandle(start, 180, 181, 179, 180.0, 1)]

    rows = build_rows(start, end, token, underlying, reference)

    assert len(rows) == 3
    assert rows[0]["nvdax_available"] == "TRUE"
    assert rows[1]["nvdax_available"] == "FALSE"
    assert rows[1]["reference_under_test_available"] == "FALSE"
    assert rows[1]["nvda_available"] == "FALSE"
    assert rows[2]["nvdax_close"] == "180.3"
