"""DexScreener adapter — live NVDAx token price without OKX.

An alternative source for the NVDAx token price that needs no API key, sidestepping
the OKX OnchainOS 402. NVDAx is an xStocks tokenized equity trading on-chain, so
DexScreener lists its pairs.

Two lookup modes:
  - by contract address (preferred, precise):
      GET https://api.dexscreener.com/latest/dex/tokens/{address}
  - by symbol search (fallback when the address is unknown):
      GET https://api.dexscreener.com/latest/dex/search?q=NVDAx

We pick the highest-USD-liquidity pair whose base token is NVDAx and read
`priceUsd`. This is a CURRENT price (good for live mode), not historical candles;
historical replay still uses James's panel.

Caveat: a DEX pool price can differ from the OKX venue price. In live mode this
becomes the token signal, so record the source in provenance and sanity-check the
scale against NVDA as usual (normalizer).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

_BASE_URL = "https://api.dexscreener.com/latest/dex"


@dataclass
class TokenQuote:
    """A current token price with market-quality context. Timestamp = fetch time."""

    price: float
    source: str  # "dexscreener"
    ts: datetime
    liquidity_usd: float | None = None
    volume_h24_usd: float | None = None
    pair_address: str | None = None
    chain: str | None = None


def _pick_best_pair(pairs: list[dict], symbol: str) -> dict | None:
    """Pure: choose the NVDAx pair with the deepest USD liquidity.

    Factored out so pair-selection is unit-testable without a network call.
    """
    candidates = [
        p
        for p in pairs
        if (p.get("baseToken") or {}).get("symbol", "").upper() == symbol.upper()
        and p.get("priceUsd")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))


def _to_quote(pair: dict) -> TokenQuote:
    return TokenQuote(
        price=float(pair["priceUsd"]),
        source="dexscreener",
        ts=datetime.now(UTC),
        liquidity_usd=float((pair.get("liquidity") or {}).get("usd") or 0) or None,
        volume_h24_usd=float((pair.get("volume") or {}).get("h24") or 0) or None,
        pair_address=pair.get("pairAddress"),
        chain=pair.get("chainId"),
    )


def get_nvdax_price(
    address: str | None = None,
    symbol: str = "NVDAx",
    client: httpx.Client | None = None,
) -> TokenQuote | None:
    """Fetch the live NVDAx token price. Returns None if unavailable.

    Uses the token-address endpoint when `address` is given, else symbol search.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=15)
    try:
        if address:
            resp = client.get(f"{_BASE_URL}/tokens/{address}")
        else:
            resp = client.get(f"{_BASE_URL}/search", params={"q": symbol})
        resp.raise_for_status()
        pairs = resp.json().get("pairs") or []
        best = _pick_best_pair(pairs, symbol)
        return _to_quote(best) if best else None
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    finally:
        if owns_client:
            client.close()
