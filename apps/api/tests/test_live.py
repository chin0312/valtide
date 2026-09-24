"""Live-mode tests: snapshot assembly (with injected sources) + graceful 503."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import valtide_api.live as live
from valtide_api.adapters.dexscreener import TokenQuote
from valtide_api.adapters.equity import RawEquityBar
from valtide_api.adapters.reference import ReferenceObservation
from valtide_api.live import LiveDataUnavailable, build_live_snapshot


def _patch_sources(monkeypatch, *, quote, bar, ref):
    monkeypatch.setattr(live.dexscreener, "get_nvdax_price", lambda **k: quote)
    monkeypatch.setattr(live.equity, "get_latest_trusted_bar", lambda *a, **k: bar)
    monkeypatch.setattr(live.reference, "get_okx_xperp_index", lambda *a, **k: ref)


def test_build_live_snapshot_with_xperp(monkeypatch):
    observation_ts = datetime(2026, 9, 19, 14, 0, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(
            price=185.1,
            source="dexscreener",
            ts=datetime(2026, 9, 19, 13, 59, tzinfo=UTC),
        ),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
            open=180, high=181, low=179, close=180.0, volume=1000,
        ),
        ref=ReferenceObservation(
            price=190.0,
            source="okx_xperp_index",
            ts=datetime(2026, 9, 19, 13, 59, tzinfo=UTC),
        ),
    )
    snap = build_live_snapshot(observation_ts=observation_ts)
    assert snap.token_price == 185.1
    assert snap.reference_under_test == 190.0
    assert snap.reference_under_test_source == "okx_xperp_index"
    assert snap.reference_under_test_ts is not None
    assert snap.reference_under_test_age_seconds is not None
    assert snap.last_trusted_reference == 180.0


def test_preserves_reference_identity_when_xperp_down(monkeypatch):
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=185.1, source="dexscreener", ts=datetime.now(UTC)),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
            open=180, high=181, low=179, close=180.0, volume=1000,
        ),
        ref=None,  # X-Perp unavailable
    )
    snap = build_live_snapshot()
    assert snap.reference_under_test is None
    assert snap.reference_under_test_source == "okx_xperp_index"
    assert snap.reference_under_test_ts is None
    assert snap.reference_under_test_age_seconds is None


def test_stale_reference_is_not_substituted_or_marked_current(monkeypatch):
    observation_ts = datetime(2026, 9, 19, 14, 0, tzinfo=UTC)
    monkeypatch.setattr(
        live,
        "get_settings",
        lambda: SimpleNamespace(
            dexscreener_nvdax_address="",
            okx_xperp_index_id="NVDA-USD",
            live_underlying_max_age_seconds=360,
            live_reference_max_age_seconds=360,
        ),
    )
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(
            price=185.1,
            source="dexscreener",
            ts=datetime(2026, 9, 19, 13, 59, tzinfo=UTC),
        ),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
            open=180,
            high=181,
            low=179,
            close=180.0,
            volume=1000,
        ),
        ref=ReferenceObservation(
            price=190.0,
            source="okx_xperp_index",
            ts=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
        ),
    )

    snap = build_live_snapshot(observation_ts=observation_ts)

    assert snap.reference_under_test is None
    assert snap.reference_under_test_source == "okx_xperp_index"
    assert snap.reference_under_test_ts == datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
    assert snap.reference_under_test_age_seconds == 64_800


def test_current_enough_underlying_is_assimilable(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
            open=181,
            high=182,
            low=180,
            close=181.0,
            volume=1000,
        ),
        ref=ReferenceObservation(
            price=181.2,
            source="okx_xperp_index",
            ts=datetime(2026, 9, 21, 14, 9, tzinfo=UTC),
        ),
    )

    snap = build_live_snapshot(observation_ts=observation_ts)

    assert snap.underlying_reference == 181.0
    assert snap.underlying_reference_ts == datetime(2026, 9, 21, 14, 5, tzinfo=UTC)
    assert snap.last_trusted_reference == 181.0
    assert snap.last_trusted_reference_ts == snap.underlying_reference_ts
    assert snap.reference_age_seconds == 300


def test_stale_underlying_remains_anchor_but_is_not_current_measurement(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 13, 55, tzinfo=UTC),
            open=180,
            high=181,
            low=179,
            close=180.0,
            volume=1000,
        ),
        ref=ReferenceObservation(
            price=181.2,
            source="okx_xperp_index",
            ts=datetime(2026, 9, 21, 14, 9, tzinfo=UTC),
        ),
    )

    snap = build_live_snapshot(observation_ts=observation_ts)

    assert snap.underlying_reference is None
    assert snap.underlying_reference_ts is None
    assert snap.last_trusted_reference == 180.0
    assert snap.last_trusted_reference_ts == datetime(2026, 9, 21, 13, 55, tzinfo=UTC)
    assert snap.reference_age_seconds == 900


def test_future_reference_is_not_current_and_provenance_is_preserved(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    future_ts = datetime(2026, 9, 21, 14, 11, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
            open=181,
            high=182,
            low=180,
            close=181.0,
            volume=1000,
        ),
        ref=ReferenceObservation(price=181.2, source="okx_xperp_index", ts=future_ts),
    )

    snap = build_live_snapshot(observation_ts=observation_ts)

    assert snap.reference_under_test is None
    assert snap.reference_under_test_ts == future_ts
    assert snap.reference_under_test_age_seconds is None


def test_future_underlying_is_rejected(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 15, tzinfo=UTC),
            open=181,
            high=182,
            low=180,
            close=181.0,
            volume=1000,
        ),
        ref=None,
    )

    with pytest.raises(LiveDataUnavailable, match="newer than"):
        build_live_snapshot(observation_ts=observation_ts)


def test_raises_when_token_price_unavailable(monkeypatch):
    _patch_sources(monkeypatch, quote=None, bar=None, ref=None)
    try:
        build_live_snapshot()
        raise AssertionError("expected LiveDataUnavailable")
    except LiveDataUnavailable:
        pass
