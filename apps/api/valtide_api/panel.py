"""Panel loader — turns James's p0_panel_5m.csv into MarketSnapshots.

James's R pipeline emits a merged 5-minute panel with these columns (build_panel.R):
    timestamp_utc, nvda_close, nvdax_close, nvdax_volume, nvda_available,
    nvdax_available, nvda_log_price, nvdax_log_price, session_state,
    time_since_nvda_min, ...

This loader replays that panel through the same pipeline as everything else.

Reference under test (Pt), per BACKEND_PLAN.md §3, self-contained in the panel:
  - when NVDA is present (open market): Pt = NVDA close  (source "nvda_live")
  - when NVDA is absent (weekend/overnight): Pt = last trusted NVDA close
    carried forward  (source "stale_nvda")
The live X-Perp index is used only in live mode; historical panels have no
historical X-Perp series, so the panel validates against NVDA / stale-NVDA.

Rows without a token price (nvdax_available == false) are skipped — there is no
challenger input, so no validation is possible.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.normalizer import assert_scale

_NA = {"", "NA", "N/A", "NaN", "nan", "null", "None"}


def _num(value: str | None) -> float | None:
    if value is None or value.strip() in _NA:
        return None
    return float(value)


def _flag(value: str | None) -> bool:
    return (value or "").strip().upper() in {"TRUE", "T", "1"}


def _parse_ts(value: str) -> datetime:
    s = value.strip().replace(" ", "T").replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def load_panel_snapshots(path: str | Path) -> list[MarketSnapshot]:
    """Build one MarketSnapshot per usable panel row (token price present)."""
    path = Path(path)
    snapshots: list[MarketSnapshot] = []

    last_close: float | None = None
    last_close_ts: datetime | None = None

    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            ts = _parse_ts(row["timestamp_utc"])
            nvda = _num(row.get("nvda_close")) if _flag(row.get("nvda_available")) else None
            nvdax = _num(row.get("nvdax_close")) if _flag(row.get("nvdax_available")) else None

            # Update the last trusted close whenever NVDA is observed.
            if nvda is not None:
                last_close, last_close_ts = nvda, ts

            # Need a token price (challenger input) and an established R0.
            if nvdax is None or last_close is None or last_close_ts is None:
                continue

            # Same unit-scale invariant the live path enforces (overlap rows only).
            assert_scale(nvdax, nvda)

            # Reference under test: live NVDA when open, else the stale close.
            if nvda is not None:
                pt, pt_source = nvda, "nvda_live"
            else:
                pt, pt_source = last_close, "stale_nvda"

            snapshots.append(
                MarketSnapshot(
                    asset="NVDAx",
                    observation_ts=ts,
                    token_price=nvdax,
                    token_volume=_num(row.get("nvdax_volume")),
                    underlying_reference=nvda,
                    underlying_reference_ts=ts if nvda is not None else None,
                    last_trusted_reference=last_close,
                    last_trusted_reference_ts=last_close_ts,
                    reference_age_seconds=int((ts - last_close_ts).total_seconds()),
                    reference_under_test=pt,
                    reference_under_test_source=pt_source,
                    market_state=_market_state(row.get("session_state")),
                    source_provenance={"panel": path.name},
                )
            )
    return snapshots


def _market_state(value: str | None) -> MarketState:
    try:
        return MarketState((value or "").strip().lower())
    except ValueError:
        return MarketState.CLOSED
