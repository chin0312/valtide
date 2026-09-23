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
from valtide_api.config import get_settings
from valtide_api.models import MarketSnapshot, MarketState, ValuationResult
from valtide_api.normalizer import assert_scale
from valtide_api.replay import run_inference
from valtide_api.session import classify


class LiveDataUnavailable(RuntimeError):
    """Raised when a required live input cannot be fetched."""


def build_live_snapshot(client: httpx.Client | None = None) -> MarketSnapshot:
    """Assemble a MarketSnapshot from the live sources. Raises if a required one fails."""
    settings = get_settings()
    now = datetime.now(UTC)

    quote = dexscreener.get_nvdax_price(
        address=settings.dexscreener_nvdax_address or None, client=client
    )
    if quote is None:
        raise LiveDataUnavailable("NVDAx token price unavailable (DexScreener).")

    last = equity.get_latest_trusted_bar("NVDA", client=client)
    if last is None:
        raise LiveDataUnavailable("NVDA underlying unavailable (Alpaca — check key/feed).")

    market_state = classify(now)
    is_open = market_state == MarketState.REGULAR
    nvda_live = last.close if is_open else None

    # Keep the selected reference identity even when its observation is unavailable.
    ref = reference.get_okx_xperp_index(settings.okx_xperp_index_id, client=client)
    if ref is not None:
        pt, pt_source, pt_ts = ref.price, ref.source, ref.ts
    else:
        pt, pt_source, pt_ts = None, "okx_xperp_index", None

    assert_scale(quote.price, nvda_live)

    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=now,
        token_price=quote.price,
        token_volume=quote.volume_h24_usd,
        underlying_reference=nvda_live,
        underlying_reference_ts=last.ts if is_open else None,
        last_trusted_reference=last.close,
        last_trusted_reference_ts=last.ts,
        reference_age_seconds=int((now - last.ts).total_seconds()),
        reference_under_test=pt,
        reference_under_test_source=pt_source,
        reference_under_test_ts=pt_ts,
        reference_under_test_age_seconds=(
            max(0, int((now - pt_ts).total_seconds())) if pt_ts is not None else None
        ),
        market_state=market_state,
        external_reference=None,
        source_provenance={
            "token": f"{quote.source}@{quote.ts.isoformat()}",
            "underlying": f"alpaca@{last.ts.isoformat()}",
            "reference_under_test": pt_source,
        },
    )


def run_live_valuation(client: httpx.Client | None = None) -> ValuationResult:
    """Build a live snapshot and run one cold-start inference.

    The merged quant runtime initializes from the latest trusted reference when it
    is available and then performs one P1a-C step. This endpoint is a cold-start /
    on-demand diagnostic, not an equivalent to a warmed sequential production
    state. It does not mutate the cache.
    """
    snapshot = build_live_snapshot(client=client)
    result, _ = run_inference(snapshot, None)
    return result
