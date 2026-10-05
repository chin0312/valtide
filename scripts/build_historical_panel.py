"""Build an asset-bound canonical five-minute market panel.

The output is generated data and is intentionally not committed. Every source
is joined by its own vendor timestamp; token and reference observations are
never forward-filled.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

# The path bootstrap intentionally precedes these first-party imports.
# isort: off
from valtide_api.assets import AssetConfig, resolve_asset_config
from valtide_api import market_sources
from valtide_api.clock import FIVE_MINUTES, require_canonical_5m
from valtide_api.session import classify
from valtide_api import token_market
# isort: on


PANEL_COLUMNS = [
    "timestamp_utc",
    "asset",
    "underlying_symbol",
    "token_source",
    "token_chain_index",
    "token_address",
    "reference_under_test_instrument",
    "reference_profile",
    "session_state",
    "token_close",
    "token_volume",
    "token_volume_usd",
    "token_available",
    "token_observed_at",
    "underlying_close",
    "underlying_available",
    "underlying_observed_at",
    "last_trusted_reference",
    "last_trusted_reference_ts",
    "reference_under_test",
    "reference_under_test_available",
    "reference_under_test_source",
    "reference_under_test_ts",
]

# Weekend and overnight tokenized-equity sessions need the most recent prior
# regular-session underlying bar, which may be several calendar days earlier.
UNDERLYING_LOOKBACK = timedelta(days=7)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return require_canonical_5m(parsed, "date-range timestamp")


def iter_grid(start: datetime, end: datetime) -> list[datetime]:
    start = require_canonical_5m(start, "start")
    end = require_canonical_5m(end, "end")
    if end < start:
        raise ValueError("end must not precede start")
    count = int((end - start) / FIVE_MINUTES) + 1
    return [start + index * FIVE_MINUTES for index in range(count)]


def build_rows(
    start, end, token_candles, underlying_bars, reference_candles, *,
    config: AssetConfig, deployment: tuple[str, str],
) -> list[dict[str, str]]:
    """Join source observations onto the canonical grid without filling gaps."""
    token_by_ts = {c.ts: c for c in token_candles}
    underlying_by_ts = {b.ts: b for b in underlying_bars}
    reference_by_ts = {c.ts: c for c in reference_candles}
    rows: list[dict[str, str]] = []
    last_underlying = max(
        (bar for bar in underlying_bars if bar.ts < start),
        key=lambda bar: bar.ts,
        default=None,
    )

    for timestamp in iter_grid(start, end):
        previous_last_underlying = last_underlying
        underlying = underlying_by_ts.get(timestamp)
        if previous_last_underlying is None:
            # No R0 anchor exists yet; dropping a pre-anchor row is different
            # from dropping a row with a missing token/reference observation.
            if underlying is not None:
                last_underlying = underlying
            continue

        token = token_by_ts.get(timestamp)
        if token is not None and token.confirm != 1:
            token = None
        # xStock remains the model input; X-Perp is separately fetched evidence.
        # A missing index candle is retained as missing and never replaced by
        # the token candle.
        ref = reference_by_ts.get(timestamp)
        rows.append(
            {
                "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
                "asset": config.asset,
                "underlying_symbol": config.underlying_symbol,
                "token_source": config.token_source,
                "token_chain_index": deployment[0],
                "token_address": deployment[1],
                "reference_under_test_instrument": config.reference_under_test_instrument,
                "reference_profile": config.reference_profile,
                "session_state": classify(timestamp).value,
                "token_close": str(token.close) if token is not None else "",
                "token_volume": str(token.volume) if token is not None else "",
                "token_volume_usd": str(token.volume_usd) if token is not None else "",
                "token_available": str(token is not None).upper(),
                "token_observed_at": (
                    token.ts.isoformat().replace("+00:00", "Z") if token is not None else ""
                ),
                "underlying_close": str(underlying.close) if underlying is not None else "",
                "underlying_available": str(underlying is not None).upper(),
                "underlying_observed_at": (
                    underlying.ts.isoformat().replace("+00:00", "Z")
                    if underlying is not None else ""
                ),
                "last_trusted_reference": str(previous_last_underlying.close),
                "last_trusted_reference_ts": previous_last_underlying.ts.isoformat().replace(
                    "+00:00", "Z"
                ),
                "reference_under_test": str(ref.close) if ref is not None else "",
                "reference_under_test_available": str(ref is not None).upper(),
                "reference_under_test_source": config.reference_under_test_source,
                "reference_under_test_ts": (
                    ref.ts.isoformat().replace("+00:00", "Z") if ref is not None else ""
                ),
            }
        )
        if underlying is not None:
            last_underlying = underlying
    return rows


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise RuntimeError("no anchored rows were available for the requested range")
    previous: datetime | None = None
    anchored = 0
    for row in rows:
        timestamp = _parse_datetime(row["timestamp_utc"])
        if previous is not None and timestamp - previous != FIVE_MINUTES:
            raise RuntimeError("panel rows must be ordered canonical five-minute observations")
        previous = timestamp
        if row.get("last_trusted_reference") and row.get("last_trusted_reference_ts"):
            anchored += 1
    if anchored == 0:
        raise RuntimeError("panel contains no anchored rows")
    identity = tuple(rows[0].get(key) for key in (
        "asset", "underlying_symbol", "token_source", "token_chain_index",
        "token_address", "reference_under_test_instrument", "reference_profile",
    ))
    if any(not value for value in identity) or any(
        tuple(row.get(key) for key in (
            "asset", "underlying_symbol", "token_source", "token_chain_index",
            "token_address", "reference_under_test_instrument", "reference_profile",
        )) != identity for row in rows
    ):
        raise RuntimeError("panel identity must be complete and constant")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=PANEL_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def build_panel(
    start: datetime,
    end: datetime,
    output: Path,
    *,
    asset: str = "NVDAx",
) -> int:
    asset_config = resolve_asset_config(asset)
    token_candles, deployment = token_market.get_historical_candles(
        asset_config, start, end
    )
    expected_deployment = (asset_config.okx_chain_index, asset_config.token_address)
    if not all(expected_deployment) or deployment != expected_deployment:
        raise RuntimeError(
            f"token adapter deployment does not match the registered identity for {asset}"
        )
    # Fetch a causal pre-range lookback so the first requested row can use a
    # strictly prior trusted underlying bar as its causal anchor. The lookback
    # is only for initialization; emitted panel rows remain within [start, end].
    underlying_bars = market_sources.underlying_historical(
        asset_config, start - UNDERLYING_LOOKBACK, end
    )
    reference_candles = market_sources.reference_historical(asset_config, start, end)
    rows = build_rows(
        start, end, token_candles, underlying_bars, reference_candles,
        config=asset_config, deployment=deployment,
    )
    _write(output, rows)
    print(f"wrote {len(rows)} anchored canonical rows to {output}")
    print(
        f"sources: token={asset_config.token_source}, "
        f"underlying={asset_config.underlying_source}_5m, "
        f"reference_under_test={asset_config.reference_under_test_source}"
    )
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="UTC canonical timestamp, e.g. 2026-09-18T14:00:00Z")
    parser.add_argument("--end", required=True, help="UTC canonical timestamp, inclusive")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--asset", default="NVDAx")
    args = parser.parse_args()
    try:
        resolve_asset_config(args.asset)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    build_panel(
        _parse_datetime(args.start),
        _parse_datetime(args.end),
        args.output,
        asset=args.asset,
    )


if __name__ == "__main__":
    main()
