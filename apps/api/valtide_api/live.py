"""Live mode — assemble an asset-scoped snapshot from configured live sources.

The selected AssetConfig supplies:
  - an exact confirmed token candle via the configured token-market adapter;
  - the configured underlying symbol and provider; and
  - the reference profile/instrument to validate.

The current NVDAx profile uses the public OKX X-Perp index. The xStock profile
uses the same token candle as its observed reference and labels that dependence.

then runs a single cold-start inference.

Timing: we value the most recently *settled* canonical bar (the boundary one
step before the current one). Its reference under test is the confirmed OKX index
candle whose open equals that boundary, exactly as the historical panel builder
joins it, so the live and backtest pipelines consume identical, causally-clean
inputs. A bar's confirmed candle exists only after it closes, which is why the
current forming bar is never valued.

Caveat: this is a one-shot estimate seeded from the model's prior, not a warmed
    filter. A warmed sequence (replay / the P1 scheduler) gives a more informative
    state; live mode is a cold-start / on-demand diagnostic.
It is compute-only and does NOT mutate the cache.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from valtide_api import market_sources, token_market
from valtide_api.assets import (
    AssetConfigurationError,
    UnsupportedAssetError,
    resolve_asset_config,
)
from valtide_api.clock import FIVE_MINUTES, canonical_5m_boundary, require_canonical_5m
from valtide_api.config import get_settings
from valtide_api.models import MarketSnapshot, MarketState, ValuationResult
from valtide_api.replay import run_inference
from valtide_api.session import classify


class LiveDataUnavailable(RuntimeError):
    """Raised when a required live input cannot be fetched."""


class ExactTokenCandleUnavailable(LiveDataUnavailable):
    """Raised when the exact confirmed token candle is not available yet."""


ExactNvdaxCandleUnavailable = ExactTokenCandleUnavailable  # compatibility import


def build_live_snapshot(
    client: httpx.Client | None = None,
    observation_ts: datetime | None = None,
    *,
    asset: str = "NVDAx",
) -> MarketSnapshot:
    """Assemble a MarketSnapshot from the live sources. Raises if a required one fails."""
    settings = get_settings()
    try:
        asset_config = resolve_asset_config(asset, settings)
    except (AssetConfigurationError, UnsupportedAssetError) as exc:
        raise LiveDataUnavailable(str(exc)) from exc
    if not asset_config.capabilities.live_data:
        raise LiveDataUnavailable(f"live data is unavailable for '{asset}'")
    try:
        token_label = token_market.source_label(asset_config)
    except AssetConfigurationError as exc:
        raise LiveDataUnavailable(str(exc)) from exc
    # Value the most recently settled bar. The current forming bar has no
    # confirmed reference candle yet, so valuing it would always drop the
    # comparator; one boundary back is settled and its candle is confirmed.
    now = observation_ts or (canonical_5m_boundary(datetime.now(UTC)) - FIVE_MINUTES)
    try:
        now = require_canonical_5m(now, "observation_ts")
    except ValueError as exc:
        raise LiveDataUnavailable(str(exc)) from exc

    try:
        token_candle = token_market.get_exact_candle(asset_config, now, client=client)
    except ExactTokenCandleUnavailable:
        raise
    except (httpx.HTTPError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise LiveDataUnavailable(
            f"{asset_config.asset} exact confirmed candle unavailable ({token_label})."
        ) from exc
    if token_candle is None:
        raise ExactTokenCandleUnavailable(
            f"{asset_config.asset} exact confirmed candle unavailable ({token_label})."
        )
    if token_candle.ts != now or token_candle.confirm != 1:
        raise LiveDataUnavailable("token adapter returned a noncanonical or unconfirmed candle")

    try:
        # Alpaca's `end` bound can include the boundary itself. Cap the query at
        # the valued bar so the next canonical boundary can never enter the
        # underlying measurement set.
        bars = market_sources.underlying_live(asset_config, client=client, now=now)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise LiveDataUnavailable(
            f"{asset_config.underlying_symbol} underlying unavailable "
            f"({asset_config.underlying_source.capitalize()} — check key/feed)."
        ) from exc
    if not bars:
        raise LiveDataUnavailable(
            f"{asset_config.underlying_symbol} underlying unavailable "
            f"({asset_config.underlying_source.capitalize()} — check key/feed)."
        )

    # The latest bar at or before the valued bar's close is the current-bucket
    # underlying measurement (underlying@T). The trusted anchor must be strictly before
    # T, exactly as the historical panel builder joins it: otherwise underlying@T would
    # seed the cold-start challenger@T init before the intended post-challenger
    # assimilation, reintroducing same-timestamp leakage on the first warmed tick.
    last = bars[-1]
    market_state = classify(now)
    underlying_age = int((now - last.ts).total_seconds())
    if underlying_age < 0:
        raise LiveDataUnavailable(
            "latest underlying bar is newer than the requested canonical observation"
        )
    is_open = market_state == MarketState.REGULAR
    underlying_current = (
        last.close
        if is_open and underlying_age <= settings.live_underlying_max_age_seconds
        else None
    )

    # Trusted anchor R0 must be the latest underlying strictly before T. If the only
    # available bar is underlying@T, do not seed challenger@T from the same
    # observation; fail the cold-start valuation instead of leaking causality.
    prior = [b for b in bars if b.ts < now]
    if not prior:
        raise LiveDataUnavailable(
            "no strictly-prior trusted underlying anchor is available for the "
            f"observation at {now.isoformat()}"
        )
    anchor = prior[-1]
    anchor_age = int((now - anchor.ts).total_seconds())

    # The cross-asset research profile compares the current observed xStock
    # against its P1a challenger. It is not an independent data source: this
    # token observation has already been assimilated by P1a before emission.
    # NVDAx retains its separately identified OKX X-Perp comparator.
    if asset_config.reference_profile == "xstock_vs_p1ac_challenger":
        ref = token_candle
        pt_source = asset_config.reference_under_test_source
        pt = ref.close if ref is not None else None
        pt_ts = ref.ts if ref is not None else None
        reference_age = 0 if ref is not None else None
    else:
        try:
            ref = market_sources.reference_live(asset_config, client=client, now=now)
        except AssetConfigurationError as exc:
            raise LiveDataUnavailable(str(exc)) from exc
        if ref is not None:
            pt, pt_source, pt_ts = ref.price, ref.source, ref.ts
            reference_age = int((now - ref.ts).total_seconds())
        else:
            pt, pt_source, pt_ts, reference_age = (
                None, asset_config.reference_under_test_source, None, None
            )

    # A gross token/underlying unit mismatch is judged by validation
    # (TOKEN_UNIT_SUSPECT), not fatally here; an economic depeg must reach the
    # Evidence State, not raise a 503.
    return MarketSnapshot(
        asset=asset_config.asset,
        observation_ts=now,
        token_price=token_candle.close,
        token_volume=token_candle.volume,
        token_volume_usd=token_candle.volume_usd,
        token_source=asset_config.token_source,
        token_observed_at=token_candle.ts,
        token_liquidity_usd=None,
        underlying_reference=underlying_current,
        underlying_reference_ts=last.ts if underlying_current is not None else None,
        last_trusted_reference=anchor.close,
        last_trusted_reference_ts=anchor.ts,
        reference_age_seconds=anchor_age,
        reference_under_test=pt,
        reference_under_test_source=pt_source,
        reference_profile=asset_config.reference_profile,
        reference_under_test_ts=pt_ts,
        reference_under_test_age_seconds=reference_age,
        market_state=market_state,
        external_reference=None,
        source_provenance={
            "token": f"{asset_config.token_source}@{token_candle.ts.isoformat()}",
            "underlying": f"{asset_config.underlying_source}@{last.ts.isoformat()}",
            "reference_under_test": (
                f"{pt_source}@{pt_ts.isoformat()}" if pt_ts is not None else pt_source
            ),
            "reference_profile": asset_config.reference_profile,
            **(
                {"reference_independence": "same_xstock_input_assimilated_by_p1a"}
                if asset_config.reference_profile == "xstock_vs_p1ac_challenger"
                else {}
            ),
        },
    )


def run_live_valuation(
    client: httpx.Client | None = None,
    observation_ts: datetime | None = None,
    *,
    asset: str = "NVDAx",
) -> ValuationResult:
    """Build a live snapshot and run one cold-start inference.

    The merged quant runtime initializes from the latest trusted reference when it
    is available and then performs one P1a-C step. This endpoint is a cold-start /
    on-demand diagnostic, not an equivalent to a warmed sequential production
    state. It does not mutate the cache.
    """
    snapshot = build_live_snapshot(
        observation_ts=observation_ts,
        client=client,
        asset=asset,
    )
    try:
        result, _ = run_inference(snapshot, None)
    except AssetConfigurationError as exc:
        raise LiveDataUnavailable(str(exc)) from exc
    return result
