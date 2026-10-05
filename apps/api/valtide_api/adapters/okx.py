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
from time import sleep
from urllib.parse import quote

import httpx

from valtide_api.assets import AssetConfig, AssetConfigurationError, resolve_asset_config
from valtide_api.config import get_settings

_BASE_URL = "https://web3.okx.com"

_deployment_lock = Lock()
_deployment_cache: dict[str, tuple[str, str]] = {}
_MAX_429_RETRIES = 2
_MAX_429_WAIT_SECONDS = 60.0
_HISTORY_PAGE_DELAY_SECONDS = 0.15


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
    for attempt in range(_MAX_429_RETRIES + 1):
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
        if resp.status_code != 429 or attempt == _MAX_429_RETRIES:
            break
        wait = _rate_limit_wait_seconds(resp)
        if wait > 0:
            sleep(wait)
    resp.raise_for_status()
    body = resp.json()
    if str(body.get("code")) != "0":
        raise RuntimeError(f"OKX API error: code={body.get('code')} msg={body.get('msg')}")
    return body["data"]


def _rate_limit_wait_seconds(response: httpx.Response) -> float:
    """Respect vendor retry/reset metadata, bounded to one minute per retry."""
    for name in ("retry-after", "ratelimit-reset", "x-ratelimit-reset"):
        value = response.headers.get(name)
        if value is None:
            continue
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            continue
        if seconds >= 0:
            return min(seconds, _MAX_429_WAIT_SECONDS)
    return 1.0


def discover_rwa_token(config: AssetConfig, client: httpx.Client | None = None) -> list[dict]:
    """Discover exact symbol/underlying matches; discovery is opt-in per asset."""
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
            if r.get("tokenSymbol") == config.asset
            or (
                config.asset == "NVDAx"
                and r.get("stockCode") in (config.underlying_symbol, config.asset)
            )
        ]
        matches.sort(key=lambda r: float(r.get("volume24h") or 0), reverse=True)
        return matches
    finally:
        if owns_client:
            client.close()


def resolve_token_deployment(
    config: AssetConfig, client: httpx.Client | None = None
) -> tuple[str, str]:
    """Prefer a pinned deployment; only explicit legacy discovery may fall back."""
    chain_index = (config.okx_chain_index or "").strip()
    token_address = (config.token_address or "").strip()
    if bool(chain_index) != bool(token_address):
        raise AssetConfigurationError("token chain index and address must be configured together")
    if chain_index and token_address:
        return chain_index, token_address
    if not config.allow_token_discovery:
        raise AssetConfigurationError(f"token deployment must be pinned for '{config.asset}'")

    with _deployment_lock:
        if config.asset in _deployment_cache:
            return _deployment_cache[config.asset]
        deployments = discover_rwa_token(config, client=client)
        if not deployments:
            raise RuntimeError(f"no deployment found for '{config.asset}' from OKX OnchainOS")
        deployment = deployments[0]
        chain_index = str(deployment.get("chainIndex") or deployment.get("chainId") or "")
        token_address = str(
            deployment.get("tokenContractAddress") or deployment.get("tokenAddress") or ""
        )
        if not chain_index or not token_address:
            raise RuntimeError("selected token deployment is missing chain index or token address")
        _deployment_cache[config.asset] = (chain_index, token_address)
        return _deployment_cache[config.asset]


def discover_nvdax(client: httpx.Client | None = None) -> list[dict]:
    """Compatibility wrapper for the existing NVDAx discovery interface."""
    return discover_rwa_token(resolve_asset_config("NVDAx"), client=client)


def resolve_nvdax_deployment(client: httpx.Client | None = None) -> tuple[str, str]:
    """Compatibility wrapper for the existing NVDAx deployment interface."""
    return resolve_token_deployment(resolve_asset_config("NVDAx"), client=client)


def clear_nvdax_deployment_cache() -> None:
    """Clear the process-local deployment cache for tests/admin refreshes."""
    with _deployment_lock:
        _deployment_cache.clear()


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
            # Historical OnchainOS calls are signed and quota-backed. Pace
            # sequential pages rather than creating a burst during backfill.
            sleep(_HISTORY_PAGE_DELAY_SECONDS)
        return [out[k] for k in sorted(out)]
    finally:
        if owns_client:
            client.close()


def get_token_candle_at(
    config: AssetConfig,
    observation_ts: datetime,
    client: httpx.Client | None = None,
) -> RawCandle | None:
    """Return only the exact confirmed token candle at ``observation_ts``.

    The live scheduler values a settled canonical five-minute bucket. This helper
    deliberately rejects neighboring, future, or unconfirmed candles instead of
    allowing a current quote to be relabeled as a historical observation.
    """
    from valtide_api.clock import require_canonical_5m

    observation_ts = require_canonical_5m(observation_ts, "observation_ts")
    chain_index, token_address = resolve_token_deployment(config, client=client)
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


def get_nvdax_candle_at(
    observation_ts: datetime, client: httpx.Client | None = None
) -> RawCandle | None:
    """Compatibility wrapper; orchestration uses the generic token boundary."""
    return get_token_candle_at(resolve_asset_config("NVDAx"), observation_ts, client=client)
