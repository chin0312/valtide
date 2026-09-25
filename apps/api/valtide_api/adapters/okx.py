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
from threading import Lock
from urllib.parse import quote

import httpx

from valtide_api.config import get_settings

_BASE_URL = "https://web3.okx.com"

_nvdax_deployment_lock = Lock()
_nvdax_deployment_cache: tuple[str, str] | None = None


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


def resolve_nvdax_deployment(client: httpx.Client | None = None) -> tuple[str, str]:
    """Resolve the canonical NVDAx deployment once for this process.

    Explicit chain/address settings are authoritative and avoid discovery. With
    no overrides, the existing deterministic RWA discovery ordering is used and
    its selected deployment is cached so a five-minute tick does not repeat the
    discovery request. The cache contains only public deployment metadata.
    """
    settings = get_settings()
    chain_index = settings.okx_nvdax_chain_index.strip()
    token_address = settings.okx_nvdax_token_address.strip()
    if bool(chain_index) != bool(token_address):
        raise ValueError(
            "OKX_NVDAX_CHAIN_INDEX and OKX_NVDAX_TOKEN_ADDRESS must be configured together"
        )
    if chain_index and token_address:
        return chain_index, token_address

    global _nvdax_deployment_cache
    with _nvdax_deployment_lock:
        if _nvdax_deployment_cache is not None:
            return _nvdax_deployment_cache
        deployments = discover_nvdax(client=client)
        if not deployments:
            raise RuntimeError("no NVDAx deployment found from OKX OnchainOS")
        deployment = deployments[0]
        chain_index = str(deployment.get("chainIndex") or deployment.get("chainId") or "")
        token_address = str(
            deployment.get("tokenContractAddress") or deployment.get("tokenAddress") or ""
        )
        if not chain_index or not token_address:
            raise RuntimeError("selected NVDAx deployment is missing chain index or token address")
        _nvdax_deployment_cache = (chain_index, token_address)
        return _nvdax_deployment_cache


def clear_nvdax_deployment_cache() -> None:
    """Clear the process-local deployment cache for tests/admin refreshes."""
    global _nvdax_deployment_cache
    with _nvdax_deployment_lock:
        _nvdax_deployment_cache = None


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


def get_nvdax_candle_at(
    observation_ts: datetime,
    client: httpx.Client | None = None,
) -> RawCandle | None:
    """Return only the exact confirmed NVDAx candle at ``observation_ts``.

    The live scheduler values a settled canonical five-minute bucket. This helper
    deliberately rejects neighboring, future, or unconfirmed candles instead of
    allowing a current quote to be relabeled as a historical observation.
    """
    from valtide_api.clock import require_canonical_5m

    observation_ts = require_canonical_5m(observation_ts, "observation_ts")
    chain_index, token_address = resolve_nvdax_deployment(client=client)
    candles = get_historical_candles(
        chain_index,
        token_address,
        observation_ts,
        observation_ts,
        bar="5m",
        client=client,
    )
    for candle in candles:
        if candle.ts == observation_ts and candle.confirm == 1:
            return candle
    return None
