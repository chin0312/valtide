"""Live mode — assemble a snapshot from live sources and run one inference.

Pulls the three live inputs (no OKX OnchainOS dependency):
  - NVDAx token price   -> DexScreener  (no key)
  - NVDA underlying      -> Alpaca
  - reference under test -> OKX X-Perp index (public)

then runs a single cold-start inference.

Caveat: this is a one-shot estimate seeded from the model's prior, not a warmed
    filter. A warmed sequence (replay / the P1 scheduler) gives a more informative
    state; live mode is a cold-start / on-demand diagnostic.
It is compute-only and does NOT mutate the cache.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from valtide_api.adapters import dexscreener, equity, reference
from valtide_api.clock import canonical_5m_boundary, require_canonical_5m
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
    now = observation_ts or canonical_5m_boundary(datetime.now(UTC))
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
        last = equity.get_latest_trusted_bar("NVDA", client=client)
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

    # Keep the selected reference identity even when its observation is unavailable.
    ref = reference.get_okx_xperp_index(settings.okx_xperp_index_id, client=client)
    if ref is not None:
        raw_reference_age = int((now - ref.ts).total_seconds())
        reference_age = raw_reference_age if raw_reference_age >= 0 else None
        reference_is_current = (
            reference_age is not None
            and reference_age <= settings.live_reference_max_age_seconds
        )
        pt = ref.price if reference_is_current else None
        pt_source, pt_ts = ref.source, ref.ts
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
