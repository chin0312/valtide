"""Small, fail-closed dispatch boundary for canonical token candles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

import httpx

from valtide_api.adapters import okx
from valtide_api.assets import AssetConfig, AssetConfigurationError


@dataclass(frozen=True)
class TokenMarketAdapter:
    label: str
    resolve: Callable[..., tuple[str, str]]
    exact: Callable[..., okx.RawCandle | None]
    historical: Callable[..., list[okx.RawCandle]]


def _okx_resolve(
    config: AssetConfig, *, client: httpx.Client | None
) -> tuple[str, str]:
    return okx.resolve_token_deployment(config, client=client)


def _okx_exact(
    config: AssetConfig, observation_ts: datetime, *, client: httpx.Client | None
) -> okx.RawCandle | None:
    return okx.get_token_candle_at(config, observation_ts, client=client)


def _okx_historical(
    chain: str, address: str, start: datetime, end: datetime, *, client: httpx.Client | None
) -> list[okx.RawCandle]:
    return okx.get_historical_candles(chain, address, start, end, client=client)


_TOKEN_MARKET_ADAPTERS = MappingProxyType({
    "okx_onchainos": TokenMarketAdapter(
        "OKX OnchainOS", _okx_resolve, _okx_exact, _okx_historical
    ),
})


def _adapter(config: AssetConfig, capability: str) -> TokenMarketAdapter:
    adapter = _TOKEN_MARKET_ADAPTERS.get(config.token_market_key)
    if not getattr(config.capabilities, capability) or adapter is None:
        raise AssetConfigurationError(f"no token-market adapter is registered for '{config.asset}'")
    return adapter


def source_label(config: AssetConfig) -> str:
    return _adapter(config, "live_data").label


def resolve_deployment(
    config: AssetConfig, *, client: httpx.Client | None = None
) -> tuple[str, str]:
    return _adapter(config, "live_data").resolve(config, client=client)


def get_exact_candle(
    config: AssetConfig, observation_ts: datetime, *, client: httpx.Client | None = None
) -> okx.RawCandle | None:
    return _adapter(config, "live_data").exact(config, observation_ts, client=client)


def get_historical_candles(
    config: AssetConfig, start: datetime, end: datetime, *, client: httpx.Client | None = None
) -> tuple[list[okx.RawCandle], tuple[str, str]]:
    adapter = _adapter(config, "historical_data")
    chain, address = adapter.resolve(config, client=client)
    return adapter.historical(chain, address, start, end, client=client), (chain, address)
