"""Reference-under-test adapter — the price Valtide independently validates.

DECISION (BACKEND_PLAN.md §3): the reference under test is the OKX X-Perp NVDA
index price. This is a DIFFERENT API from OnchainOS:

  - NVDAx token price  -> OKX OnchainOS   (web3.okx.com, signed)   [okx.py]
  - X-Perp index price -> OKX exchange v5 (www.okx.com/api/v5/...) [this module]

CONFIRMED (2026-09-22): the v5 index-tickers endpoint is public (no auth) and
the NVDA X-Perp instId is "NVDA-USD". Verified response:
  {"code":"0","data":[{"instId":"NVDA-USD","idxPx":"228.51","ts":"1790089804702",...}]}
Price is read from "idxPx"; "ts" is a millisecond UTC timestamp.

If the index is unreachable this returns None; callers preserve the intended
reference identity and mark validation INCONCLUSIVE rather than substituting a
different reference.
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


@dataclass
class RawReferenceCandle:
    """One completed OKX X-Perp index candle."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    confirm: int


class ReferenceHistoryUnavailable(RuntimeError):
    """Raised when the public OKX history endpoint cannot provide history."""


def get_okx_xperp_index(
    index_id: str = _DEFAULT_INDEX_ID, client: httpx.Client | None = None
) -> ReferenceObservation | None:
    """Fetch the OKX X-Perp index price via the v5 market-data API.

    Returns None if the endpoint is unreachable or returns no data. The caller
    then preserves the reference identity and marks validation
    INCONCLUSIVE/COMPARATOR_UNAVAILABLE.
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


def get_okx_xperp_index_candles(
    index_id: str = _DEFAULT_INDEX_ID,
    start: datetime | None = None,
    end: datetime | None = None,
    bar: str = "5m",
    client: httpx.Client | None = None,
) -> list[RawReferenceCandle]:
    """Fetch completed historical X-Perp index candles with backward pagination."""
    if start is None or end is None:
        raise ValueError("start and end are required for historical index candles")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("historical index candle bounds must be timezone-aware")
    start_ms = int(start.astimezone(UTC).timestamp() * 1000)
    end_ms = int(end.astimezone(UTC).timestamp() * 1000)
    if end_ms < start_ms:
        raise ValueError("historical index candle end must not precede start")

    owns_client = client is None
    client = client or httpx.Client(timeout=30, transport=httpx.HTTPTransport(retries=5))
    cursor: str | None = str(end_ms)
    seen_oldest = float("inf")
    out: dict[int, RawReferenceCandle] = {}
    try:
        while True:
            params = {"instId": index_id, "bar": bar, "limit": "100", "after": cursor}
            try:
                response = client.get(
                    f"{_V5_BASE_URL}/api/v5/market/history-index-candles", params=params
                )
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict):
                    raise ReferenceHistoryUnavailable(
                        "OKX history-index-candles response was not an object"
                    )
                if str(body.get("code")) != "0":
                    raise ReferenceHistoryUnavailable(
                        "OKX history-index-candles error: "
                        f"code={body.get('code')} msg={body.get('msg')}"
                    )
                rows = body.get("data") or []
                if not isinstance(rows, list):
                    raise ReferenceHistoryUnavailable(
                        "OKX history-index-candles data was not an array"
                    )
            except ReferenceHistoryUnavailable:
                raise
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                raise ReferenceHistoryUnavailable(
                    "OKX history-index-candles request failed"
                ) from exc

            if not rows:
                break
            for row in rows:
                if not isinstance(row, list):
                    raise ReferenceHistoryUnavailable(
                        "OKX history-index-candles row was not an array"
                    )
                if len(row) < 6:
                    raise ReferenceHistoryUnavailable("OKX history-index-candles row is incomplete")
                try:
                    ts_ms = int(row[0])
                    confirm = int(row[5])
                except (TypeError, ValueError) as exc:
                    raise ReferenceHistoryUnavailable(
                        "OKX history-index-candles row has invalid timestamp/status"
                    ) from exc
                if confirm != 1 or not (start_ms <= ts_ms <= end_ms):
                    continue
                try:
                    out[ts_ms] = RawReferenceCandle(
                        ts=datetime.fromtimestamp(ts_ms / 1000, tz=UTC),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        confirm=confirm,
                    )
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ReferenceHistoryUnavailable(
                        "OKX history-index-candles row has invalid prices"
                    ) from exc

            oldest = min(int(row[0]) for row in rows)
            if oldest <= start_ms or oldest >= seen_oldest:
                break
            seen_oldest = oldest
            cursor = str(oldest)
        return [out[key] for key in sorted(out)]
    finally:
        if owns_client:
            client.close()
