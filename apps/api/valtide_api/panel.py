"""Panel loader for James's canonical 5-minute market dataset."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.normalizer import assert_scale

_NA = {"", "NA", "N/A", "NaN", "nan", "null", "None"}
_FIVE_MINUTES = 300


class PanelTimestampError(ValueError):
    """Raised when a panel is not an ordered canonical 5-minute sequence."""


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
    """Build one snapshot per row after a trusted reference is established.

    Missing token observations remain in the sequence as ``token_price=None``.
    This preserves the quant runtime's 5-minute state transition without
    fabricating a token price or silently introducing a state gap.
    """
    path = Path(path)
    snapshots: list[MarketSnapshot] = []
    last_close: float | None = None
    last_close_ts: datetime | None = None
    previous_ts: datetime | None = None

    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            ts = _parse_ts(row["timestamp_utc"])
            if previous_ts is not None:
                delta = (ts - previous_ts).total_seconds()
                if delta != _FIVE_MINUTES:
                    raise PanelTimestampError(
                        "panel timestamps must advance by exactly 5 minutes; "
                        f"got {delta:g} seconds between {previous_ts.isoformat()} "
                        f"and {ts.isoformat()}"
                    )
            previous_ts = ts

            nvda = _num(row.get("nvda_close")) if _flag(row.get("nvda_available")) else None
            nvdax = (
                _num(row.get("nvdax_close")) if _flag(row.get("nvdax_available")) else None
            )

            if nvda is not None:
                last_close, last_close_ts = nvda, ts

            # A quant step needs an R0 anchor. Rows before the first trusted
            # underlying observation cannot be represented honestly.
            if last_close is None or last_close_ts is None:
                continue

            if nvdax is not None:
                assert_scale(nvdax, nvda)

            if nvda is not None:
                reference, reference_source = nvda, "nvda_live"
                reference_ts = ts
                reference_age = 0
            else:
                reference, reference_source = last_close, "stale_nvda"
                reference_ts = last_close_ts
                reference_age = int((ts - last_close_ts).total_seconds())

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
                    reference_under_test=reference,
                    reference_under_test_source=reference_source,
                    reference_under_test_ts=reference_ts,
                    reference_under_test_age_seconds=reference_age,
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
