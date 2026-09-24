#!/usr/bin/env python3
"""Run safe, read-only checks against a deployed Valtide backend."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

TIMEOUT_SECONDS = 10
EXPECTED_CHAIN_ID = 1952


@dataclass(frozen=True)
class CheckResult:
    status: int | None
    payload: object | None
    error: str | None = None


def _get(base_url: str, path: str) -> CheckResult:
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read()
            status = int(response.status)
    except HTTPError as exc:
        # The status is enough for a concise, safe smoke report. Do not print the
        # response body because deployment errors can contain implementation detail.
        return CheckResult(status=int(exc.code), payload=None)
    except (OSError, URLError, TimeoutError) as exc:
        return CheckResult(status=None, payload=None, error=type(exc).__name__)

    try:
        return CheckResult(status=status, payload=json.loads(body))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return CheckResult(status=status, payload=None, error="invalid_json")


def _valid_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise argparse.ArgumentTypeError("backend URL must include an http(s) scheme and host")
    return value.rstrip("/")


def _status(result: CheckResult) -> str:
    if result.status is None:
        return result.error or "request_failed"
    return str(result.status)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend_url", type=_valid_base_url)
    args = parser.parse_args()

    failures = 0

    health = _get(args.backend_url, "/health")
    health_ok = (
        health.status == 200
        and isinstance(health.payload, dict)
        and health.payload.get("status") == "ok"
    )
    print(f"health: {'PASS' if health_ok else 'FAIL'} ({_status(health)})")
    failures += not health_ok

    assets = _get(args.backend_url, "/api/assets")
    assets_ok = assets.status == 200 and isinstance(assets.payload, list)
    asset_count = len(assets.payload) if isinstance(assets.payload, list) else 0
    print(
        f"assets: {'PASS' if assets_ok else 'FAIL'} ({_status(assets)}; "
        f"{asset_count} asset(s))"
    )
    failures += not assets_ok

    runtime = _get(args.backend_url, "/api/runtime/NVDAx")
    if runtime.status == 200 and isinstance(runtime.payload, dict):
        warmed = bool(
            runtime.payload.get("has_state") or runtime.payload.get("has_live_result")
        )
        runtime_state = "warmed" if warmed else "not warmed yet (non-fatal)"
        print(f"runtime: PASS ({runtime_state})")
    else:
        print(f"runtime: unavailable ({_status(runtime)}; non-fatal)")

    onchain = _get(args.backend_url, "/api/onchain/NVDAx")
    if onchain.status == 200 and isinstance(onchain.payload, dict):
        chain_id = onchain.payload.get("chain_id")
        onchain_ok = chain_id == EXPECTED_CHAIN_ID
        print(
            f"onchain: {'PASS' if onchain_ok else 'FAIL'} "
            f"(chain_id={chain_id!r})"
        )
        failures += not onchain_ok
    else:
        print(f"onchain: unavailable ({_status(onchain)}; non-fatal)")

    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
