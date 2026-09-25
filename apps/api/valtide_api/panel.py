"""Loader for canonical five-minute historical market panels."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from valtide_api.clock import require_canonical_5m
from valtide_api.models import MarketSnapshot, MarketState

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
    """Build one snapshot per canonical row after an R0 anchor is established.

    Missing token observations remain in the sequence as ``token_price=None``.
    This preserves the quant runtime's 5-minute state transition without
    fabricating a token price or silently introducing a state gap. New real
    panels should provide explicit reference-under-test columns; older fixtures
    retain their explicit stale-NVDA fallback semantics.
    """
    path = Path(path)
    snapshots: list[MarketSnapshot] = []
    last_close: float | None = None
    last_close_ts: datetime | None = None
    previous_ts: datetime | None = None

    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            try:
                ts = require_canonical_5m(_parse_ts(row["timestamp_utc"]), "panel timestamp")
            except ValueError as exc:
                raise PanelTimestampError(str(exc)) from exc
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

            # Validate explicit provenance timestamps even on an anchor-only
            # row that will not be emitted as a public snapshot.
            if (
                "reference_under_test_available" in row
                and _flag(row.get("reference_under_test_available"))
                and row.get("reference_under_test_ts")
            ):
                reference_ts = _parse_ts(row["reference_under_test_ts"])
                if reference_ts > ts:
                    raise PanelTimestampError(
                        "reference-under-test timestamp must not be after its panel observation"
                    )

            # Capture the strictly prior trusted anchor before constructing
            # this row so current NVDA cannot become same-timestamp R0.
            previous_last_close = last_close
            previous_last_close_ts = last_close_ts
            if previous_last_close is None or previous_last_close_ts is None:
                explicit_anchor = _num(row.get("last_trusted_reference"))
                explicit_anchor_ts = (
                    _parse_ts(row["last_trusted_reference_ts"])
                    if row.get("last_trusted_reference_ts")
                    else None
                )
                if explicit_anchor is not None and explicit_anchor_ts is not None:
                    if explicit_anchor_ts >= ts:
                        raise PanelTimestampError(
                            "last trusted reference timestamp must be strictly before "
                            "its panel observation"
                        )
                    previous_last_close = explicit_anchor
                    previous_last_close_ts = explicit_anchor_ts

            # The first trusted underlying row establishes the anchor only;
            # it is not a public/evaluable challenger observation.
            if previous_last_close is None or previous_last_close_ts is None:
                if nvda is not None:
                    last_close, last_close_ts = nvda, ts
                continue

            # A gross token/underlying unit mismatch is now judged per-snapshot by
            # validation (TOKEN_UNIT_SUSPECT); a real economic depeg must survive
            # panel assembly and reach the Evidence State, never crash the replay.
            (
                reference,
                reference_source,
                reference_ts,
                reference_age,
            ) = _reference_fields(
                row,
                ts,
                nvda,
                previous_last_close,
                previous_last_close_ts,
            )

            snapshots.append(
                MarketSnapshot(
                    asset="NVDAx",
                    observation_ts=ts,
                    token_price=nvdax,
                    token_volume=_num(row.get("nvdax_volume")),
                    token_volume_usd=_num(row.get("nvdax_volume_usd")),
                    token_source="okx_onchainos" if nvdax is not None else None,
                    token_observed_at=ts if nvdax is not None else None,
                    underlying_reference=nvda,
                    underlying_reference_ts=ts if nvda is not None else None,
                    last_trusted_reference=previous_last_close,
                    last_trusted_reference_ts=previous_last_close_ts,
                    reference_age_seconds=int((ts - previous_last_close_ts).total_seconds()),
                    reference_under_test=reference,
                    reference_under_test_source=reference_source,
                    reference_under_test_ts=reference_ts,
                    reference_under_test_age_seconds=reference_age,
                    market_state=_market_state(row.get("session_state"), ts),
                    source_provenance={
                        "panel": path.name,
                        "token": "okx_onchainos" if nvdax is not None else "",
                        "reference_under_test": reference_source,
                    },
                )
            )

            # Make the current underlying available as the trusted anchor for
            # the next canonical observation, never for this one.
            if nvda is not None:
                last_close, last_close_ts = nvda, ts
    return snapshots


def _reference_fields(
    row: dict[str, str],
    timestamp: datetime,
    current_underlying: float | None,
    last_close: float,
    last_close_ts: datetime,
) -> tuple[float | None, str, datetime | None, int | None]:
    """Read an explicit reference-under-test when present, else legacy fields."""
    if "reference_under_test_available" in row:
        source = (row.get("reference_under_test_source") or "reference_under_test").strip()
        available = _flag(row.get("reference_under_test_available"))
        if not available:
            return None, source, None, None
        reference = _num(row.get("reference_under_test"))
        if reference is None:
            return None, source, None, None
        reference_ts = (
            _parse_ts(row["reference_under_test_ts"])
            if row.get("reference_under_test_ts")
            else timestamp
        )
        if reference_ts > timestamp:
            raise PanelTimestampError(
                "reference-under-test timestamp must not be after its panel observation"
            )
        age = int((timestamp - reference_ts).total_seconds())
        return reference, source, reference_ts, age

    if current_underlying is not None:
        return current_underlying, "nvda_live", timestamp, 0
    return last_close, "stale_nvda", last_close_ts, max(
        0, int((timestamp - last_close_ts).total_seconds())
    )


def _market_state(value: str | None, timestamp: datetime) -> MarketState:
    if not value:
        from valtide_api.session import classify

        return classify(timestamp)
    try:
        return MarketState((value or "").strip().lower())
    except ValueError:
        from valtide_api.session import classify

        return classify(timestamp)
