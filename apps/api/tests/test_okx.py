"""Deterministic tests for the canonical OKX NVDAx live-candle boundary."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

import valtide_api.adapters.okx as okx
from valtide_api import token_market
from valtide_api.assets import resolve_asset_config
from valtide_api.config import Settings


def _candle(ts: datetime, *, confirm: int = 1, close: float = 181.0) -> okx.RawCandle:
    return okx.RawCandle(ts, close, close, close, close, 12.0, 345.0, confirm)


def test_exact_helper_accepts_only_confirmed_requested_timestamp(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    config = resolve_asset_config("NVDAx", Settings(_env_file=None))
    monkeypatch.setattr(
        okx,
        "discover_rwa_token",
        lambda _config, client=None: [{
            "chainIndex": "196",
            "tokenContractAddress": "0xabc",
        }],
    )
    monkeypatch.setattr(
        okx,
        "get_historical_candles",
        lambda *args, **kwargs: [
            _candle(observation_ts + timedelta(minutes=5), close=999.0),
            _candle(observation_ts, close=181.2),
        ],
    )
    okx.clear_nvdax_deployment_cache()

    result = okx.get_token_candle_at(config, observation_ts)

    assert result is not None
    assert result.ts == observation_ts
    assert result.close == 181.2


@pytest.mark.parametrize(
    "candles",
    [
        lambda ts: [_candle(ts, confirm=0)],
        lambda ts: [_candle(ts + timedelta(minutes=5))],
        lambda ts: [_candle(ts - timedelta(minutes=5))],
    ],
)
def test_exact_helper_rejects_unconfirmed_neighboring_or_future_candles(
    monkeypatch, candles
):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    config = resolve_asset_config(
        "NVDAx",
        Settings(_env_file=None, okx_nvdax_chain_index="196", okx_nvdax_token_address="0xabc"),
    )
    monkeypatch.setattr(
        okx,
        "get_historical_candles",
        lambda *args, **kwargs: candles(observation_ts),
    )

    assert okx.get_token_candle_at(config, observation_ts) is None


def test_explicit_deployment_override_bypasses_discovery(monkeypatch):
    settings = Settings(_env_file=None,
        okx_nvdax_chain_index="196",
        okx_nvdax_token_address="0xexplicit",
    )
    config = resolve_asset_config("NVDAx", settings)
    monkeypatch.setattr(
        okx,
        "discover_rwa_token",
        lambda **kwargs: pytest.fail("discovery should be bypassed"),
    )

    assert okx.resolve_token_deployment(config) == ("196", "0xexplicit")


def test_discovered_deployment_is_cached(monkeypatch):
    config = resolve_asset_config("NVDAx", Settings(_env_file=None))
    calls = 0

    def discover(_config, client=None):
        nonlocal calls
        calls += 1
        return [{"chainIndex": "196", "tokenContractAddress": "0xcached"}]

    monkeypatch.setattr(okx, "discover_rwa_token", discover)
    okx.clear_nvdax_deployment_cache()
    assert okx.resolve_token_deployment(config) == ("196", "0xcached")
    assert okx.resolve_token_deployment(config) == ("196", "0xcached")
    assert calls == 1
    okx.clear_nvdax_deployment_cache()


def test_generic_token_adapter_uses_pinned_synthetic_deployment(monkeypatch):
    ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    base = resolve_asset_config("NVDAx", Settings(_env_file=None))
    synthetic = replace(
        base, asset="TESTx", underlying_symbol="TEST", okx_chain_index="777",
        token_address="0xsynthetic", allow_token_discovery=False,
    )
    requested = []

    def candles(chain, address, start, end, **_kwargs):
        requested.append((chain, address, start, end))
        return [_candle(ts, confirm=1)]

    monkeypatch.setattr(okx, "get_historical_candles", candles)
    assert token_market.get_exact_candle(synthetic, ts).ts == ts
    assert requested == [("777", "0xsynthetic", ts, ts)]
    with pytest.raises(ValueError, match="deployment must be pinned"):
        token_market.resolve_deployment(
            replace(synthetic, okx_chain_index=None, token_address=None)
        )


def test_generic_token_adapter_rejects_unconfirmed_candle(monkeypatch):
    ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    config = resolve_asset_config(
        "NVDAx",
        Settings(_env_file=None, okx_nvdax_chain_index="501", okx_nvdax_token_address="0xtest"),
    )
    monkeypatch.setattr(okx, "get_historical_candles", lambda *_a, **_k: [_candle(ts, confirm=0)])
    assert token_market.get_exact_candle(config, ts) is None
