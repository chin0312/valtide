"""Reference-under-test adapter — the price Valtide independently validates.

DECISION (BACKEND_PLAN.md §3): the reference under test is the OKX X-Perp NVDA
index price. This is a DIFFERENT API from OnchainOS:

  - NVDAx token price  -> OKX OnchainOS   (web3.okx.com, signed)   [okx.py]
  - X-Perp index price -> OKX exchange v5 (www.okx.com/api/v5/...) [this module]

CONFIRMED (2026-09-22): the v5 index-tickers endpoint is public (no auth) and
the NVDA X-Perp instId is "NVDA-USD". Verified response:
  {"code":"0","data":[{"instId":"NVDA-USD","idxPx":"228.51","ts":"1790089804702",...}]}
Price is read from "idxPx"; "ts" is a millisecond UTC timestamp.

If the index is unreachable this returns None; callers (panel/live) fall back to
the stale NVDA close themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

_V5_BASE_URL = "https://www.okx.com"

# The X-Perp index instId to confirm from the builder kit. Placeholder default.
_DEFAULT_INDEX_ID = "NVDA-USD"


@dataclass
class ReferenceObservation:
    """A named reference price with provenance. See ARCHITECTURE §8.2."""

    price: float
    source: str  # e.g. "okx_xperp_index"
    ts: datetime


def get_okx_xperp_index(
    index_id: str = _DEFAULT_INDEX_ID, client: httpx.Client | None = None
) -> ReferenceObservation | None:
    """Fetch the OKX X-Perp index price via the v5 market-data API.

    Returns None if the endpoint is unreachable or returns no data, so the
    caller can fall back or mark the reference INCONCLUSIVE/COMPARATOR_UNAVAILABLE.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=15)
    try:
        resp = client.get(
            f"{_V5_BASE_URL}/api/v5/market/index-tickers",
            params={"instId": index_id},
        )
        resp.raise_for_status()
        body = resp.json()
        if str(body.get("code")) != "0" or not body.get("data"):
            return None
        row = body["data"][0]
        return ReferenceObservation(
            price=float(row["idxPx"]),
            source="okx_xperp_index",
            ts=datetime.fromtimestamp(int(row["ts"]) / 1000, tz=UTC),
        )
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    finally:
        if owns_client:
            client.close()
