"""Live-mode tests: snapshot assembly (with injected sources) + graceful 503."""

from datetime import UTC, datetime

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
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=185.1, source="dexscreener", ts=datetime.now(UTC)),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
            open=180, high=181, low=179, close=180.0, volume=1000,
        ),
        ref=ReferenceObservation(price=190.0, source="okx_xperp_index", ts=datetime.now(UTC)),
    )
    snap = build_live_snapshot()
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


def test_raises_when_token_price_unavailable(monkeypatch):
    _patch_sources(monkeypatch, quote=None, bar=None, ref=None)
    try:
        build_live_snapshot()
        raise AssertionError("expected LiveDataUnavailable")
    except LiveDataUnavailable:
        pass
