"""Alpaca adapter — NVDA underlying equity bars.

Python port of James's R helper (valtide-r-pipeline/R/api_alpaca.R). Same source
as his training, so the live path does not drift from the research path.

Endpoint:  GET https://data.alpaca.markets/v2/stocks/{symbol}/bars
Auth:      APCA-API-KEY-ID / APCA-API-SECRET-KEY headers
Feed:      "sip" (full market, needs paid plan) or "iex" (free tier). Default
           follows settings.alpaca_feed; free accounts should use "iex".

Vendor field names (t/o/h/l/c/v/n/vw) never escape this module — callers get
RawEquityBar objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from valtide_api.config import get_settings

_BASE_URL = "https://data.alpaca.markets/v2/stocks"


@dataclass
class RawEquityBar:
    """One Alpaca stock bar. Timestamp UTC, prices as floats."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
    }


def get_stock_bars(
    symbol: str,
    start: datetime,
    end: datetime,
    timeframe: str = "5Min",
    feed: str | None = None,
    adjustment: str = "raw",
    client: httpx.Client | None = None,
) -> list[RawEquityBar]:
    """Fetch bars for a symbol over [start, end], paginating via next_page_token."""
    settings = get_settings()
    feed = feed or settings.alpaca_feed
    owns_client = client is None
    client = client or httpx.Client(timeout=30, transport=httpx.HTTPTransport(retries=5))

    bars: list[RawEquityBar] = []
    page_token: str | None = None
    try:
        while True:
            params = {
                "timeframe": timeframe,
                "start": start.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "end": end.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "limit": 10000,
                "adjustment": adjustment,
                "feed": feed,
                "sort": "asc",
            }
            if page_token:
                params["page_token"] = page_token

            resp = client.get(f"{_BASE_URL}/{symbol}/bars", headers=_headers(), params=params)
            resp.raise_for_status()
            body = resp.json()

            for b in body.get("bars") or []:
                bars.append(
                    RawEquityBar(
                        ts=datetime.fromisoformat(b["t"].replace("Z", "+00:00")),
                        open=float(b["o"]),
                        high=float(b["h"]),
                        low=float(b["l"]),
                        close=float(b["c"]),
                        volume=float(b["v"]),
                        vwap=float(b["vw"]) if "vw" in b else None,
                    )
                )

            page_token = body.get("next_page_token")
            if not page_token:
                break
        return bars
    finally:
        if owns_client:
            client.close()


def get_trusted_bars(
    symbol: str = "NVDA",
    lookback_days: int = 5,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> list[RawEquityBar]:
    """Return trusted underlying bars in the lookback window, ascending by ts.

    These are R0 anchor candidates, not necessarily official regular-session
    closes. The end of the query is the current time; live.py decides which bar
    is the current-bucket measurement and which strictly-prior bar is the trusted
    anchor. Exchange-calendar and US-holiday selection remain outside this adapter.
    """
    query_now = now or datetime.now(UTC)
    if query_now.tzinfo is None:
        raise ValueError("trusted-bar query time must be timezone-aware")
    query_now = query_now.astimezone(UTC)
    start = query_now - timedelta(days=lookback_days)
    end = query_now
    return get_stock_bars(symbol, start, end, client=client)


def get_latest_trusted_bar(
    symbol: str = "NVDA",
    lookback_days: int = 5,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> RawEquityBar | None:
    """Return the latest available trusted underlying bar in the lookback window."""
    bars = get_trusted_bars(symbol, lookback_days, client=client, now=now)
    return bars[-1] if bars else None
