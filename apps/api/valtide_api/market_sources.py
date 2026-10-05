"""Configured underlying and reference adapter dispatch for live and panels."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

import httpx

from valtide_api.adapters import equity, reference
from valtide_api.assets import AssetConfig, AssetConfigurationError


@dataclass(frozen=True)
class SourceAdapter:
    live: Callable[..., object]
    historical: Callable[..., object]


def _alpaca_live(config: AssetConfig, *, client: httpx.Client | None, now: datetime):
    return equity.get_trusted_bars(config.underlying_symbol, client=client, now=now)


def _alpaca_historical(config: AssetConfig, start: datetime, end: datetime):
    return equity.get_stock_bars(config.underlying_symbol, start, end)


def _okx_index_live(config: AssetConfig, *, client: httpx.Client | None, now: datetime):
    return reference.get_confirmed_index_bar(
        now, config.reference_under_test_instrument, client=client
    )


def _okx_index_historical(config: AssetConfig, start: datetime, end: datetime):
    return reference.get_okx_xperp_index_candles(
        start=start, end=end, index_id=config.reference_under_test_instrument
    )


_UNDERLYING = MappingProxyType({"alpaca": SourceAdapter(_alpaca_live, _alpaca_historical)})
_REFERENCE = MappingProxyType({
    "okx_xperp_index": SourceAdapter(_okx_index_live, _okx_index_historical)
})


def underlying_live(config: AssetConfig, *, client: httpx.Client | None, now: datetime):
    adapter = _UNDERLYING.get(config.underlying_source)
    if adapter is None:
        raise AssetConfigurationError(f"underlying source is unavailable for '{config.asset}'")
    return adapter.live(config, client=client, now=now)


def underlying_historical(config: AssetConfig, start: datetime, end: datetime):
    adapter = _UNDERLYING.get(config.underlying_source)
    if adapter is None:
        raise AssetConfigurationError(f"underlying source is unavailable for '{config.asset}'")
    return adapter.historical(config, start, end)


def reference_live(config: AssetConfig, *, client: httpx.Client | None, now: datetime):
    adapter = _REFERENCE.get(config.reference_under_test_source)
    if adapter is None:
        raise AssetConfigurationError(f"reference source is unavailable for '{config.asset}'")
    return adapter.live(config, client=client, now=now)


def reference_historical(config: AssetConfig, start: datetime, end: datetime):
    adapter = _REFERENCE.get(config.reference_under_test_source)
    if adapter is None:
        raise AssetConfigurationError(f"reference source is unavailable for '{config.asset}'")
    return adapter.historical(config, start, end)
