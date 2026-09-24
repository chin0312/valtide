"""Deterministic tests for the public OKX reference-history adapter."""

from datetime import UTC, datetime

import httpx
import pytest

from valtide_api.adapters.reference import (
    ReferenceHistoryUnavailable,
    get_confirmed_index_bar,
    get_okx_xperp_index_candles,
)


def test_history_adapter_paginates_filters_and_sorts_completed_rows():
    start = datetime(2026, 9, 22, 13, 55, tzinfo=UTC)
    end = datetime(2026, 9, 22, 14, 10, tzinfo=UTC)
    requests: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        after = int(request.url.params["after"])
        if after > 1790086200000:
            return httpx.Response(
                200,
                json={
                    "code": "0",
                    "data": [
                        ["1790086200000", "184", "185", "183", "184.5", "1"],
                        ["1790085900000", "183", "184", "182", "183.5", "0"],
                        ["1790085600000", "182", "183", "181", "182.5", "1"],
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [["1790085300000", "181", "182", "180", "181.5", "1"]],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    candles = get_okx_xperp_index_candles(start=start, end=end, client=client)

    assert len(requests) == 2
    assert requests[0]["after"] == str(int(end.timestamp() * 1000) + 1)
    assert requests[1]["after"] == "1790085600000"
    assert [c.confirm for c in candles] == [1, 1, 1]
    assert [c.ts for c in candles] == sorted(c.ts for c in candles)
    assert all(start <= candle.ts <= end for candle in candles)
    assert end in [candle.ts for candle in candles]


def test_history_adapter_surfaces_http_failures():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"code": "500", "msg": "temporarily unavailable"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ReferenceHistoryUnavailable):
        get_okx_xperp_index_candles(
            start=datetime(2026, 9, 19, 14, 0, tzinfo=UTC),
            end=datetime(2026, 9, 19, 14, 5, tzinfo=UTC),
            client=client,
        )


def test_confirmed_index_bar_returns_close_for_the_exact_boundary():
    boundary = datetime(2026, 9, 22, 14, 0, tzinfo=UTC)
    boundary_ms = int(boundary.timestamp() * 1000)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    [str(boundary_ms), "184", "185", "183", "184.5", "1"],
                    [str(boundary_ms - 300_000), "182", "183", "181", "182.5", "1"],
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    obs = get_confirmed_index_bar(boundary, client=client)

    assert obs is not None
    assert obs.ts == boundary
    assert obs.price == 184.5  # candle close, not open
    assert obs.source == "okx_xperp_index"


def test_confirmed_index_bar_is_none_when_boundary_candle_unconfirmed():
    boundary = datetime(2026, 9, 22, 14, 0, tzinfo=UTC)
    boundary_ms = int(boundary.timestamp() * 1000)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    [str(boundary_ms), "184", "185", "183", "184.5", "0"],
                    [str(boundary_ms - 300_000), "182", "183", "181", "182.5", "1"],
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert get_confirmed_index_bar(boundary, client=client) is None


def test_confirmed_index_bar_is_none_on_history_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"code": "500", "msg": "temporarily unavailable"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert (
        get_confirmed_index_bar(datetime(2026, 9, 22, 14, 0, tzinfo=UTC), client=client)
        is None
    )
