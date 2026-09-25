"""Durable warmed operational valuation-history tests."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

import valtide_api.routes.history as history_route
from valtide_api.main import app
from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.replay import replay
from valtide_api.runtime_store import RuntimeStore
from valtide_api.scheduler import run_live_tick

_ANCHOR = datetime(2026, 9, 21, 14, 0, tzinfo=UTC)


def _snapshot(timestamp: datetime) -> MarketSnapshot:
    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=timestamp,
        token_price=181.1,
        token_volume=12.0,
        token_volume_usd=345.0,
        token_source="okx_onchainos",
        token_observed_at=timestamp,
        underlying_reference=181.0,
        underlying_reference_ts=timestamp,
        last_trusted_reference=180.0,
        last_trusted_reference_ts=timestamp - timedelta(minutes=5),
        reference_age_seconds=300,
        reference_under_test=181.2,
        reference_under_test_source="okx_xperp_index",
        reference_under_test_ts=timestamp,
        reference_under_test_age_seconds=0,
        market_state=MarketState.REGULAR,
        source_provenance={
            "token": f"okx_onchainos@{timestamp.isoformat()}",
            "underlying": "alpaca",
            "reference_under_test": "okx_xperp_index",
        },
    )


def _builder(snapshots):
    by_ts = {snapshot.observation_ts: snapshot for snapshot in snapshots}

    def build(*, observation_ts):
        return by_ts[observation_ts]

    return build


def test_successful_tick_persists_one_history_row_and_duplicate_does_not_duplicate(tmp_path):
    timestamp = _ANCHOR + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    builder = _builder([_snapshot(timestamp)])

    first = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)
    duplicate = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)

    history = store.load_history("NVDAx")
    assert first.status == "success"
    assert duplicate.status == "already_processed"
    assert len(history) == 1
    assert history[0] == first.result
    assert store.load_runtime("NVDAx").latest_result == history[0]


def test_failed_tick_does_not_append_history(tmp_path):
    timestamp = _ANCHOR + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    def failing_builder(*, observation_ts):  # noqa: ARG001
        raise RuntimeError("synthetic source outage")

    failed = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=failing_builder)

    assert failed.status == "failure"
    assert store.load_history("NVDAx") == []


def test_history_is_chronological_limited_and_survives_restart(tmp_path):
    timestamps = [_ANCHOR + timedelta(minutes=5 * index) for index in range(1, 4)]
    path = tmp_path / "runtime.sqlite3"
    store = RuntimeStore(path)
    builder = _builder([_snapshot(timestamp) for timestamp in timestamps])

    for timestamp in timestamps:
        assert run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder).status == (
            "success"
        )
    assert [result.timestamp for result in store.load_history("NVDAx", limit=2)] == timestamps[1:]
    store.close()

    restarted = RuntimeStore(path)
    assert [result.timestamp for result in restarted.load_history("NVDAx")] == timestamps


def test_history_limit_is_bounded(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder = _builder([_snapshot(timestamp)])
    run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)

    for limit in (0, 2017):
        try:
            store.load_history("NVDAx", limit=limit)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid history limit was accepted")


def test_history_route_is_read_only_and_rejects_unknown_assets(monkeypatch, tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder = _builder([_snapshot(timestamp)])
    run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)
    monkeypatch.setattr(history_route, "get_runtime_store", lambda: store)

    client = TestClient(app)
    response = client.get("/api/history/NVDAx?limit=72")
    unknown = client.get("/api/history/FOOx")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["source_provenance"]["token"].startswith("okx_onchainos@")
    assert unknown.status_code == 404
    assert len(store.load_history("NVDAx")) == 1


def test_replay_does_not_write_operational_history(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    results = replay([_snapshot(_ANCHOR + timedelta(minutes=5))])

    assert results
    assert store.load_history("NVDAx") == []
