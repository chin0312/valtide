"""Tests for the canonical historical-panel join."""

from datetime import UTC, datetime, timedelta

import scripts.build_historical_panel as historical_panel
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
    underlying = [
        RawEquityBar(start - timedelta(minutes=5), 179, 180, 178, 179.0, 900),
        RawEquityBar(start, 180, 181, 179, 180.0, 1000),
    ]
    reference = [RawReferenceCandle(start, 180, 181, 179, 180.0, 1)]

    rows = build_rows(start, end, token, underlying, reference)

    assert len(rows) == 3
    assert rows[0]["nvdax_available"] == "TRUE"
    assert rows[1]["nvdax_available"] == "FALSE"
    assert rows[1]["reference_under_test_available"] == "FALSE"
    assert rows[1]["nvda_available"] == "FALSE"
    assert rows[2]["nvdax_close"] == "180.3"
    assert rows[0]["last_trusted_reference"] == "179.0"
    assert rows[0]["last_trusted_reference_ts"].endswith("13:55:00Z")


def test_panel_builder_fetches_underlying_lookback_for_anchor(monkeypatch, tmp_path):
    start = datetime(2026, 9, 22, 14, 0, tzinfo=UTC)
    end = datetime(2026, 9, 22, 14, 5, tzinfo=UTC)
    requested_ranges = []

    monkeypatch.setattr(historical_panel.okx, "discover_nvdax", lambda: [{
        "chainIndex": "196",
        "tokenContractAddress": "0xabc",
    }])
    monkeypatch.setattr(
        historical_panel.okx,
        "get_historical_candles",
        lambda *args: [],
    )

    def fake_stock_bars(symbol, fetch_start, fetch_end):
        requested_ranges.append((symbol, fetch_start, fetch_end))
        return [RawEquityBar(fetch_start, 179, 180, 178, 179.0, 900)]

    monkeypatch.setattr(historical_panel.equity, "get_stock_bars", fake_stock_bars)
    monkeypatch.setattr(
        historical_panel.reference,
        "get_okx_xperp_index_candles",
        lambda **kwargs: [],
    )

    output = tmp_path / "panel.csv"
    assert historical_panel.build_panel(start, end, output) == 2
    assert requested_ranges == [("NVDA", start - timedelta(minutes=60), end)]
