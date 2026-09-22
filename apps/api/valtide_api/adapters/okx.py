"""OKX OnchainOS adapter — NVDAx token market data.

Direct Python port of James's R helper (valtide-r-pipeline/R/api_okx.R). Auth is
HMAC-SHA256 request signing:

    prehash   = timestamp + "GET" + requestPathWithQuery
    signature = base64(hmac_sha256(prehash, secret))
    headers   = OK-ACCESS-KEY / SIGN / TIMESTAMP / PASSPHRASE

Vendor field names must not escape this module — callers get RawCandle objects.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote

import httpx

from valtide_api.config import get_settings

_BASE_URL = "https://web3.okx.com"


@dataclass
class RawCandle:
    """One OKX historical candle. Timestamps in UTC. Prices as floats."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    volume_usd: float
    confirm: int


def _timestamp() -> str:
    """ISO-8601 UTC with millisecond precision, e.g. 2026-09-22T13:00:00.123Z."""
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _query_string(params: dict[str, str | None]) -> str:
    kept = {k: v for k, v in params.items() if v not in (None, "")}
    if not kept:
        return ""
    parts = [f"{quote(k, safe='')}={quote(str(v), safe='')}" for k, v in kept.items()]
    return "?" + "&".join(parts)


def _sign(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _get(path: str, params: dict[str, str | None], client: httpx.Client) -> dict | list:
    settings = get_settings()
    query = _query_string(params)
    path_with_query = path + query
    ts = _timestamp()
    signature = _sign(ts + "GET" + path_with_query, settings.okx_api_secret)

    resp = client.get(
        _BASE_URL + path_with_query,
        headers={
            "OK-ACCESS-KEY": settings.okx_api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": settings.okx_api_passphrase,
        },
    )
    resp.raise_for_status()
    body = resp.json()
    if str(body.get("code")) != "0":
        raise RuntimeError(f"OKX API error: code={body.get('code')} msg={body.get('msg')}")
    return body["data"]


def discover_nvdax(client: httpx.Client | None = None) -> list[dict]:
    """Return NVDAx deployments from the RWA token list, ordered by 24h volume.

    Mirrors James's discover_nvdax(): issuer/category filters, then match on
    tokenSymbol == 'NVDAx'. Caller picks the highest-volume deployment.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=30, transport=httpx.HTTPTransport(retries=5))
    try:
        rows = _get(
            "/api/v6/dex/market/rwa/tokens",
            {"issuer": "36", "category": "47", "limit": "100"},
            client,
        )
        data = rows.get("list", []) if isinstance(rows, dict) else rows
        matches = [
            r
            for r in data
            if r.get("tokenSymbol") == "NVDAx" or r.get("stockCode") in ("NVDA", "NVDAx")
        ]
        matches.sort(key=lambda r: float(r.get("volume24h") or 0), reverse=True)
        return matches
    finally:
        if owns_client:
            client.close()


def get_historical_candles(
    chain_index: str,
    token_address: str,
    start: datetime,
    end: datetime,
    bar: str = "5m",
    client: httpx.Client | None = None,
) -> list[RawCandle]:
    """Fetch 5-minute candles for a deployment, paginating backwards like the R code."""
    owns_client = client is None
    client = client or httpx.Client(timeout=30, transport=httpx.HTTPTransport(retries=5))
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    after: str | None = None
    seen_oldest = float("inf")
    out: dict[int, RawCandle] = {}
    try:
        while True:
            data = _get(
                "/api/v6/dex/market/historical-candles",
                {
                    "chainIndex": chain_index,
                    "tokenContractAddress": token_address,
                    "after": after,
                    "bar": bar,
                    "limit": "299",
                },
                client,
            )
            if not data:
                break
            for row in data:
                ts_ms = int(row[0])
                if not (start_ms <= ts_ms <= end_ms):
                    continue
                out[ts_ms] = RawCandle(
                    ts=datetime.fromtimestamp(ts_ms / 1000, tz=UTC),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    volume_usd=float(row[6]),
                    confirm=int(row[7]),
                )
            oldest = min(int(row[0]) for row in data)
            if oldest <= start_ms or oldest >= seen_oldest:
                break
            seen_oldest = oldest
            after = str(oldest)
        return [out[k] for k in sorted(out)]
    finally:
        if owns_client:
            client.close()
