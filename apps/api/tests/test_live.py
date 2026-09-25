"""Live-mode tests: settled-bar snapshot assembly with injected sources.

The live path values the most recently settled canonical bar and sources the
reference under test from the confirmed OKX index candle whose open equals that
bar (ts == observation_ts, age 0), identical to the historical panel join.
"""

from datetime import UTC, datetime

import pytest

import valtide_api.live as live
from valtide_api.adapters.dexscreener import TokenQuote
from valtide_api.adapters.equity import RawEquityBar
from valtide_api.adapters.okx import RawCandle
from valtide_api.adapters.reference import ReferenceObservation
from valtide_api.clock import FIVE_MINUTES, canonical_5m_boundary, is_canonical_5m
from valtide_api.live import LiveDataUnavailable, build_live_snapshot, run_live_valuation


def _patch_sources(monkeypatch, *, quote, bar, ref, bars=None, candle=None):
    """Patch the exact token candle, underlying bars, and reference for the bar.

    `bar` is the single latest trusted bar (back-compat); pass `bars` to supply the
    full ascending window when the current-bucket and trusted-anchor bars differ.
    """
    trusted = bars if bars is not None else ([bar] if bar is not None else [])
    def get_candle(boundary, **_kwargs):
        if quote is None:
            return None
        return candle or RawCandle(
            boundary,
            quote.price,
            quote.price,
            quote.price,
            quote.price,
            quote.volume_h24_usd or 100.0,
            quote.volume_h24_usd or 100.0,
            1,
        )

    monkeypatch.setattr(live.okx, "get_nvdax_candle_at", get_candle)
    monkeypatch.setattr(live.equity, "get_trusted_bars", lambda *a, **k: trusted)
    monkeypatch.setattr(live.reference, "get_confirmed_index_bar", lambda *a, **k: ref)


def test_build_live_snapshot_uses_confirmed_reference_candle(monkeypatch):
    observation_ts = datetime(2026, 9, 19, 14, 0, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(
            price=185.1,
            source="dexscreener",
            ts=datetime(2026, 9, 19, 14, 5, tzinfo=UTC),
        ),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
            open=180, high=181, low=179, close=180.0, volume=1000,
        ),
        # Confirmed candle for the valued bar: ts == observation_ts.
        ref=ReferenceObservation(
            price=190.0, source="okx_xperp_index", ts=observation_ts
        ),
    )
    snap = build_live_snapshot(observation_ts=observation_ts)
    assert snap.token_price == 185.1
    assert snap.reference_under_test == 190.0
    assert snap.reference_under_test_source == "okx_xperp_index"
    assert snap.reference_under_test_ts == observation_ts
    # The confirmed candle opens at the valued bar, so its age is always zero.
    assert snap.reference_under_test_age_seconds == 0
    assert snap.last_trusted_reference == 180.0


def test_preserves_reference_identity_when_candle_unconfirmed(monkeypatch):
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=185.1, source="dexscreener", ts=datetime.now(UTC)),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
            open=180, high=181, low=179, close=180.0, volume=1000,
        ),
        ref=None,  # confirmed candle not yet available / endpoint unreachable
    )
    snap = build_live_snapshot()
    assert snap.reference_under_test is None
    assert snap.reference_under_test_source == "okx_xperp_index"
    assert snap.reference_under_test_ts is None
    assert snap.reference_under_test_age_seconds is None


def test_missing_reference_is_not_substituted_by_underlying(monkeypatch):
    """A missing confirmed candle stays INCONCLUSIVE; NVDA never stands in for it."""
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=None,
        bars=[
            RawEquityBar(
                ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
                open=180, high=181, low=179, close=180.0, volume=1000,
            ),
            RawEquityBar(
                ts=observation_ts,
                open=181, high=182, low=180, close=181.0, volume=1000,
            ),
        ],
        ref=None,
    )
    snap = build_live_snapshot(observation_ts=observation_ts)
    # Underlying is current and assimilable, but it must not become the reference.
    assert snap.underlying_reference == 181.0
    assert snap.reference_under_test is None
    assert snap.reference_under_test_source == "okx_xperp_index"


def test_confirmed_reference_yields_a_comparator_not_inconclusive(monkeypatch):
    """Regression: a live-shaped snapshot with a confirmed candle validates the
    reference instead of emitting COMPARATOR_UNAVAILABLE."""
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
            open=181, high=182, low=180, close=181.0, volume=1000,
        ),
        ref=ReferenceObservation(
            price=181.2, source="okx_xperp_index", ts=observation_ts
        ),
    )
    result = run_live_valuation(observation_ts=observation_ts)
    assert result.reference_under_test == 181.2
    assert "COMPARATOR_UNAVAILABLE" not in result.reason_codes


def test_current_enough_underlying_is_assimilable(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
            open=181, high=182, low=180, close=181.0, volume=1000,
        ),
        ref=ReferenceObservation(
            price=181.2, source="okx_xperp_index", ts=observation_ts
        ),
    )

    snap = build_live_snapshot(observation_ts=observation_ts)

    assert snap.underlying_reference == 181.0
    assert snap.underlying_reference_ts == datetime(2026, 9, 21, 14, 5, tzinfo=UTC)
    assert snap.last_trusted_reference == 181.0
    assert snap.last_trusted_reference_ts == snap.underlying_reference_ts
    assert snap.reference_age_seconds == 300


def test_cold_start_anchor_is_strictly_prior_bar_not_same_timestamp(monkeypatch):
    """Regression (PR #5): on the first warmed/cold-start tick the trusted anchor
    must be the NVDA bar strictly before T, never NVDA@T. With bars at 14:05 and
    14:10, challenger@14:10 initializes from the 14:05 anchor while NVDA@14:10 is
    used only as the underlying_reference for post-challenger assimilation."""
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=None,
        bars=[
            RawEquityBar(
                ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
                open=180, high=181, low=179, close=180.0, volume=1000,
            ),
            RawEquityBar(
                ts=datetime(2026, 9, 21, 14, 10, tzinfo=UTC),
                open=181, high=182, low=180, close=181.0, volume=1000,
            ),
        ],
        ref=ReferenceObservation(
            price=181.2, source="okx_xperp_index", ts=observation_ts
        ),
    )

    snap = build_live_snapshot(observation_ts=observation_ts)

    # Trusted anchor R0 = strictly prior NVDA (14:05), never the same-timestamp bar.
    assert snap.last_trusted_reference == 180.0
    assert snap.last_trusted_reference_ts == datetime(2026, 9, 21, 14, 5, tzinfo=UTC)
    assert snap.last_trusted_reference_ts < observation_ts
    assert snap.reference_age_seconds == 300
    # NVDA@T is only the current underlying measurement for post-challenger assimilation.
    assert snap.underlying_reference == 181.0
    assert snap.underlying_reference_ts == observation_ts


def test_cold_start_without_prior_anchor_fails_explicitly(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=None,
        bars=[
            RawEquityBar(
                ts=observation_ts,
                open=181,
                high=182,
                low=180,
                close=181.0,
                volume=1000,
            )
        ],
        ref=ReferenceObservation(
            price=181.2, source="okx_xperp_index", ts=observation_ts
        ),
    )

    with pytest.raises(LiveDataUnavailable, match="strictly-prior trusted underlying anchor"):
        build_live_snapshot(observation_ts=observation_ts)

    with pytest.raises(LiveDataUnavailable, match="strictly-prior trusted underlying anchor"):
        run_live_valuation(observation_ts=observation_ts)


def test_stale_underlying_remains_anchor_but_is_not_current_measurement(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 13, 55, tzinfo=UTC),
            open=180, high=181, low=179, close=180.0, volume=1000,
        ),
        ref=ReferenceObservation(
            price=181.2, source="okx_xperp_index", ts=observation_ts
        ),
    )

    snap = build_live_snapshot(observation_ts=observation_ts)

    assert snap.underlying_reference is None
    assert snap.underlying_reference_ts is None
    assert snap.last_trusted_reference == 180.0
    assert snap.last_trusted_reference_ts == datetime(2026, 9, 21, 13, 55, tzinfo=UTC)
    assert snap.reference_age_seconds == 900


def test_future_underlying_is_rejected(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 15, tzinfo=UTC),
            open=181, high=182, low=180, close=181.0, volume=1000,
        ),
        ref=None,
    )

    with pytest.raises(LiveDataUnavailable, match="newer than"):
        build_live_snapshot(observation_ts=observation_ts)


def test_underlying_query_is_capped_at_observation_boundary(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    all_bars = [
        RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
            open=180,
            high=181,
            low=179,
            close=180.0,
            volume=1000,
        ),
        RawEquityBar(
            ts=observation_ts,
            open=181,
            high=182,
            low=180,
            close=181.0,
            volume=1000,
        ),
        RawEquityBar(
            ts=observation_ts + FIVE_MINUTES,
            open=182,
            high=183,
            low=181,
            close=182.0,
            volume=1000,
        ),
    ]
    query_ends = []

    def get_bars(*_args, now=None, **_kwargs):
        query_ends.append(now)
        return [bar for bar in all_bars if bar.ts <= now]

    monkeypatch.setattr(
        live.okx,
        "get_nvdax_candle_at",
        lambda boundary, **_k: RawCandle(
            boundary, 181.0, 182.0, 180.0, 181.1, 1000.0, 181_100.0, 1
        ),
    )
    monkeypatch.setattr(live.equity, "get_trusted_bars", get_bars)
    monkeypatch.setattr(
        live.reference,
        "get_confirmed_index_bar",
        lambda *_a, **_k: ReferenceObservation(
            price=181.2, source="okx_xperp_index", ts=observation_ts
        ),
    )

    snapshot = build_live_snapshot(observation_ts=observation_ts)

    assert query_ends == [observation_ts]
    assert snapshot.last_trusted_reference_ts < observation_ts
    assert snapshot.underlying_reference_ts == observation_ts


def test_default_observation_values_the_settled_bar(monkeypatch):
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="dexscreener", ts=datetime.now(UTC)),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
            open=180, high=181, low=179, close=180.0, volume=1000,
        ),
        ref=None,
    )
    before = canonical_5m_boundary(datetime.now(UTC)) - FIVE_MINUTES
    snap = build_live_snapshot()
    after = canonical_5m_boundary(datetime.now(UTC)) - FIVE_MINUTES

    assert is_canonical_5m(snap.observation_ts)
    # One boundary before the current one (allowing a boundary rollover mid-test).
    assert snap.observation_ts in {before, after}


def test_gross_scale_divergence_does_not_raise(monkeypatch):
    # A large token/underlying gap must reach validation, not blow up assembly.
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=185.1, source="dexscreener", ts=observation_ts),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
            open=60, high=61, low=59, close=60.0, volume=1000,
        ),
        ref=ReferenceObservation(
            price=60.0, source="okx_xperp_index", ts=observation_ts
        ),
    )
    snap = build_live_snapshot(observation_ts=observation_ts)
    assert snap.token_price == 185.1
    assert snap.underlying_reference == 60.0


def test_live_snapshot_carries_okx_token_volumes_without_liquidity(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    _patch_sources(
        monkeypatch,
        quote=TokenQuote(price=181.1, source="unused", ts=observation_ts),
        candle=RawCandle(
            observation_ts,
            181.0,
            182.0,
            180.0,
            181.1,
            42.0,
            7_654.0,
            1,
        ),
        bar=RawEquityBar(
            ts=datetime(2026, 9, 21, 14, 5, tzinfo=UTC),
            open=181, high=182, low=180, close=181.0, volume=1000,
        ),
        ref=ReferenceObservation(
            price=181.2, source="okx_xperp_index", ts=observation_ts
        ),
    )
    snap = build_live_snapshot(observation_ts=observation_ts)
    assert snap.token_source == "okx_onchainos"
    assert snap.token_observed_at == observation_ts
    assert snap.token_volume == 42.0
    assert snap.token_volume_usd == 7_654.0
    assert snap.token_liquidity_usd is None


def test_raises_when_token_price_unavailable(monkeypatch):
    _patch_sources(monkeypatch, quote=None, bar=None, ref=None)
    with pytest.raises(LiveDataUnavailable):
        build_live_snapshot()


def test_missing_exact_okx_candle_does_not_fall_back_to_dexscreener(
    monkeypatch,
):
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
            ts=observation_ts,
        ),
    )
    monkeypatch.setattr(live.okx, "get_nvdax_candle_at", lambda *_a, **_k: None)

    with pytest.raises(LiveDataUnavailable, match="OKX OnchainOS"):
        build_live_snapshot(observation_ts=observation_ts)
