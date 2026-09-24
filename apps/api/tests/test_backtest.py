"""Historical-panel backtest metric tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

import valtide_api.routes.backtest as backtest_route
from valtide_api.main import app
from valtide_api.models import MarketSnapshot, MarketState


def _snapshot(timestamp: datetime, underlying: float | None) -> MarketSnapshot:
    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=timestamp,
        token_price=180.1,
        token_volume=50_000.0,
        underlying_reference=underlying,
        underlying_reference_ts=timestamp if underlying is not None else None,
        last_trusted_reference=180.0,
        last_trusted_reference_ts=timestamp,
        reference_age_seconds=0,
        reference_under_test=180.0,
        reference_under_test_source="okx_xperp_index",
        reference_under_test_ts=timestamp,
        reference_under_test_age_seconds=0,
        market_state=MarketState.CLOSED,
    )


def test_historical_backtest_reports_metrics_for_evaluable_rows(monkeypatch):
    timestamps = [
        datetime(2026, 9, 19, 14, 0, tzinfo=UTC),
        datetime(2026, 9, 19, 14, 5, tzinfo=UTC),
    ]
    snapshots = [_snapshot(timestamps[0], 180.0), _snapshot(timestamps[1], None)]
    monkeypatch.setattr(
        backtest_route,
        "resolve_snapshots",
        lambda **_: (snapshots, "historical_panel"),
    )

    response = TestClient(app).get("/api/backtest/NVDAx?source=panel")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "historical"
    assert body["n_observations"] == 2
    assert body["n_evaluable"] == 1
    assert body["mae"] is not None
    assert body["rmse"] is not None
    assert body["interval_coverage"] is not None


def test_scenario_backtest_does_not_claim_ground_truth_metrics(monkeypatch):
    snapshots = [_snapshot(datetime(2026, 9, 19, 14, 0, tzinfo=UTC), 180.0)]
    monkeypatch.setattr(
        backtest_route,
        "resolve_snapshots",
        lambda **_: (snapshots, "scenario"),
    )

    response = TestClient(app).get("/api/backtest/NVDAx?source=scenario")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "scenario"
    assert body["n_evaluable"] == 0
    assert body["mae"] is None
    assert body["rmse"] is None
    assert body["interval_coverage"] is None
