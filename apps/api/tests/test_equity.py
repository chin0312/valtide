"""Deterministic tests for the Alpaca underlying-bar adapter."""

from datetime import UTC, datetime

import httpx

from valtide_api.adapters.equity import get_latest_trusted_bar


def test_latest_trusted_bar_queries_through_current_time():
    now = datetime(2026, 9, 24, 14, 10, tzinfo=UTC)
    requests: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(dict(request.url.params))
        return httpx.Response(200, json={"bars": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert get_latest_trusted_bar(now=now, client=client) is None

    assert len(requests) == 1
    assert requests[0]["start"] == "2026-09-19T14:10:00Z"
    assert requests[0]["end"] == "2026-09-24T14:10:00Z"
