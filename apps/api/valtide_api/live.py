"""Live mode — assemble a snapshot from live sources and run one inference.

Pulls the three live inputs (no OKX OnchainOS dependency):
  - NVDAx token price   -> DexScreener  (no key)
  - NVDA underlying      -> Alpaca
  - reference under test -> OKX X-Perp confirmed index candle (public)

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

from valtide_api.adapters import dexscreener, equity, reference
from valtide_api.clock import FIVE_MINUTES, canonical_5m_boundary, require_canonical_5m
from valtide_api.config import get_settings
from valtide_api.models import MarketSnapshot, MarketState, ValuationResult
from valtide_api.normalizer import assert_scale
from valtide_api.replay import run_inference
from valtide_api.session import classify


class LiveDataUnavailable(RuntimeError):
    """Raised when a required live input cannot be fetched."""


def build_live_snapshot(
    client: httpx.Client | None = None,
    observation_ts: datetime | None = None,
) -> MarketSnapshot:
    """Assemble a MarketSnapshot from the live sources. Raises if a required one fails."""
    settings = get_settings()
    # Value the most recently settled bar. The current forming bar has no
    # confirmed reference candle yet, so valuing it would always drop the
    # comparator; one boundary back is settled and its candle is confirmed.
    now = observation_ts or (canonical_5m_boundary(datetime.now(UTC)) - FIVE_MINUTES)
    try:
        now = require_canonical_5m(now, "observation_ts")
    except ValueError as exc:
        raise LiveDataUnavailable(str(exc)) from exc

    quote = dexscreener.get_nvdax_price(
        address=settings.dexscreener_nvdax_address or None, client=client
    )
    if quote is None:
        raise LiveDataUnavailable("NVDAx token price unavailable (DexScreener).")

    try:
        # Cap the query at the valued bar's close so a newer bar can never be
        # mistaken for this bar's underlying measurement.
        last = equity.get_latest_trusted_bar("NVDA", client=client, now=now + FIVE_MINUTES)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise LiveDataUnavailable(
            "NVDA underlying unavailable (Alpaca — check key/feed)."
        ) from exc
    if last is None:
        raise LiveDataUnavailable("NVDA underlying unavailable (Alpaca — check key/feed).")

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

    # Reference under test: the confirmed OKX X-Perp index candle opening at the
    # valued bar (ts == now, age 0), identical to the historical panel join. When
    # it is not yet confirmed or unreachable, keep the reference identity and let
    # validation mark COMPARATOR_UNAVAILABLE rather than substituting NVDA.
    ref = reference.get_confirmed_index_bar(now, settings.okx_xperp_index_id, client=client)
    if ref is not None:
        pt, pt_source, pt_ts = ref.price, ref.source, ref.ts
        reference_age = int((now - ref.ts).total_seconds())
    else:
        pt, pt_source, pt_ts, reference_age = None, "okx_xperp_index", None, None

    try:
        assert_scale(quote.price, underlying_current)
    except ValueError as exc:
        raise LiveDataUnavailable(f"live token/underlying scale check failed: {exc}") from exc

    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=now,
        token_price=quote.price,
        token_volume=quote.volume_h24_usd,
        underlying_reference=underlying_current,
        underlying_reference_ts=last.ts if underlying_current is not None else None,
        last_trusted_reference=last.close,
        last_trusted_reference_ts=last.ts,
        reference_age_seconds=underlying_age,
        reference_under_test=pt,
        reference_under_test_source=pt_source,
        reference_under_test_ts=pt_ts,
        reference_under_test_age_seconds=reference_age,
        market_state=market_state,
        external_reference=None,
        source_provenance={
            "token": f"{quote.source}@{quote.ts.isoformat()}",
            "underlying": f"alpaca@{last.ts.isoformat()}",
            "reference_under_test": (
                f"{pt_source}@{pt_ts.isoformat()}" if pt_ts is not None else pt_source
            ),
        },
    )


def run_live_valuation(
    client: httpx.Client | None = None,
    observation_ts: datetime | None = None,
) -> ValuationResult:
    """Build a live snapshot and run one cold-start inference.

    The merged quant runtime initializes from the latest trusted reference when it
    is available and then performs one P1a-C step. This endpoint is a cold-start /
    on-demand diagnostic, not an equivalent to a warmed sequential production
    state. It does not mutate the cache.
    """
    snapshot = build_live_snapshot(observation_ts=observation_ts, client=client)
    result, _ = run_inference(snapshot, None)
    return result
