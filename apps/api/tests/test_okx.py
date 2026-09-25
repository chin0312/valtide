"""Deterministic tests for the canonical OKX NVDAx live-candle boundary."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import valtide_api.adapters.okx as okx


def _candle(ts: datetime, *, confirm: int = 1, close: float = 181.0) -> okx.RawCandle:
    return okx.RawCandle(ts, close, close, close, close, 12.0, 345.0, confirm)


def test_exact_helper_accepts_only_confirmed_requested_timestamp(monkeypatch):
    observation_ts = datetime(2026, 9, 21, 14, 10, tzinfo=UTC)
    monkeypatch.setattr(
        okx,
        "get_settings",
        lambda: SimpleNamespace(okx_nvdax_chain_index="", okx_nvdax_token_address=""),
    )
    monkeypatch.setattr(
        okx,
        "discover_nvdax",
        lambda client=None: [{
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

    result = okx.get_nvdax_candle_at(observation_ts)

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
    monkeypatch.setattr(
        okx,
        "get_settings",
        lambda: SimpleNamespace(okx_nvdax_chain_index="196", okx_nvdax_token_address="0xabc"),
    )
    monkeypatch.setattr(
        okx,
        "get_historical_candles",
        lambda *args, **kwargs: candles(observation_ts),
    )

    assert okx.get_nvdax_candle_at(observation_ts) is None


def test_explicit_deployment_override_bypasses_discovery(monkeypatch):
    settings = SimpleNamespace(
        okx_nvdax_chain_index="196",
        okx_nvdax_token_address="0xexplicit",
    )
    monkeypatch.setattr(okx, "get_settings", lambda: settings)
    monkeypatch.setattr(
        okx,
        "discover_nvdax",
        lambda **kwargs: pytest.fail("discovery should be bypassed"),
    )

    assert okx.resolve_nvdax_deployment() == ("196", "0xexplicit")


def test_discovered_deployment_is_cached(monkeypatch):
    settings = SimpleNamespace(okx_nvdax_chain_index="", okx_nvdax_token_address="")
    calls = 0

    def discover(client=None):
        nonlocal calls
        calls += 1
        return [{"chainIndex": "196", "tokenContractAddress": "0xcached"}]

    monkeypatch.setattr(okx, "get_settings", lambda: settings)
    monkeypatch.setattr(okx, "discover_nvdax", discover)
    okx.clear_nvdax_deployment_cache()

    assert okx.resolve_nvdax_deployment() == ("196", "0xcached")
    assert okx.resolve_nvdax_deployment() == ("196", "0xcached")
    assert calls == 1
    okx.clear_nvdax_deployment_cache()
