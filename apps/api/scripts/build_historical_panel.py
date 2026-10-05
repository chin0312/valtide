"""Build the backend's canonical NVDA historical replay panel.

The builder keeps a strictly prior underlying anchor separate from the current
underlying observation. Missing token/reference values are represented as
missing rows rather than forward-filled. It is intentionally small and
deterministic so the API tests and the research pipeline share the same join
semantics.
"""

from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from valtide_api.adapters import equity, okx, reference
from valtide_api.session import classify

_FIVE_MINUTES = timedelta(minutes=5)


def _grid(start: datetime, end: datetime) -> Iterable[datetime]:
    current = start.astimezone(UTC)
    finish = end.astimezone(UTC)
    while current <= finish:
        yield current
        current += _FIVE_MINUTES


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def build_rows(
    start: datetime,
    end: datetime,
    token: list[okx.RawCandle],
    underlying: list[equity.RawEquityBar],
    reference_history: list[reference.RawReferenceCandle],
) -> list[dict[str, str]]:
    """Join exact five-minute observations after establishing a prior anchor."""

    token_by_ts = {item.ts.astimezone(UTC): item for item in token}
    underlying_by_ts = {item.ts.astimezone(UTC): item for item in underlying}
    reference_by_ts = {item.ts.astimezone(UTC): item for item in reference_history}
    prior_candidates = sorted(
        (item for item in underlying if item.ts.astimezone(UTC) < start.astimezone(UTC)),
        key=lambda item: item.ts,
    )
    anchor = prior_candidates[-1] if prior_candidates else None
    rows: list[dict[str, str]] = []

    for timestamp in _grid(start, end):
        timestamp = timestamp.astimezone(UTC)
        current_underlying = underlying_by_ts.get(timestamp)
        current_token = token_by_ts.get(timestamp)
        current_reference = reference_by_ts.get(timestamp)
        if anchor is None:
            # A row without a prior trusted anchor cannot enter replay. The
            # writer will fail closed if the whole requested range is unanchored.
            if current_underlying is not None:
                anchor = current_underlying
            continue

        row: dict[str, str] = {
            "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
            "nvda_close": _fmt(current_underlying.close if current_underlying else None),
            "nvda_available": _bool(current_underlying is not None),
            "nvda_volume": _fmt(current_underlying.volume if current_underlying else None),
            "nvda_vwap": _fmt(current_underlying.vwap if current_underlying else None),
            "nvdax_close": _fmt(current_token.close if current_token else None),
            "nvdax_available": _bool(current_token is not None),
            "nvdax_volume": _fmt(current_token.volume if current_token else None),
            "nvdax_volume_usd": _fmt(current_token.volume_usd if current_token else None),
            "reference_under_test": _fmt(current_reference.close if current_reference else None),
            "reference_under_test_available": _bool(current_reference is not None),
            "reference_under_test_source": "okx_xperp_index",
            "reference_under_test_ts": (
                current_reference.ts.isoformat().replace("+00:00", "Z")
                if current_reference
                else ""
            ),
            "underlying_reference": _fmt(current_underlying.close if current_underlying else None),
            "underlying_reference_available": _bool(current_underlying is not None),
            "last_trusted_reference": _fmt(anchor.close),
            "last_trusted_reference_ts": (
                anchor.ts.astimezone(UTC).isoformat().replace("+00:00", "Z")
            ),
            "session_state": classify(timestamp).value,
        }
        rows.append(row)

        # The current underlying becomes eligible only for the next row.
        if current_underlying is not None:
            anchor = current_underlying

    return rows


def _write(path: str | Path, rows: list[dict[str, str]]) -> None:
    """Validate and atomically replace a panel file."""

    destination = Path(path)
    if not rows:
        raise RuntimeError("no anchored rows; refusing to replace the existing panel")
    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, destination)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def build_panel(start: datetime, end: datetime, output: str | Path) -> int:
    """Fetch and write a canonical NVDA panel; return the written row count."""

    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("panel bounds must be timezone-aware")
    chain_index, token_address = okx.resolve_nvdax_deployment()
    token = okx.get_historical_candles(chain_index, token_address, start, end)
    underlying = equity.get_stock_bars("NVDA", start - timedelta(days=7), end)
    reference_history = reference.get_okx_xperp_index_candles(
        index_id="NVDA-USD", start=start, end=end
    )
    rows = build_rows(start, end, token, underlying, reference_history)
    _write(output, rows)
    return len(rows)


if __name__ == "__main__":
    raise SystemExit(
        "Import build_panel or provide an explicit caller; no implicit live fetch is run."
    )
