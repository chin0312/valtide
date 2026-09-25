"""Market-session classifier.

Pure function, no I/O. Maps a UTC timestamp to one of the five research regimes
James's model expects (see docs/BACKEND_ARCHITECTURE.md). Uses NYSE
regular hours in US Eastern time, which handles EST/EDT automatically via the
zoneinfo database.

P0 scope: weekends -> CLOSED. A full US market-holiday calendar (e.g. via the
`holidays` package) is a P1 refinement; for the demo the weekend rule is what
matters, and holidays are noted as a known gap rather than silently wrong.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from valtide_api.models import MarketState

_ET = ZoneInfo("America/New_York")

# NYSE session boundaries in Eastern time.
_PREMARKET_OPEN = time(4, 0)
_REGULAR_OPEN = time(9, 30)
_REGULAR_CLOSE = time(16, 0)
_AFTERHOURS_CLOSE = time(20, 0)


def classify(ts: datetime) -> MarketState:
    """Classify a timezone-aware UTC timestamp into a MarketState.

    Raises if given a naive datetime — we never guess a timezone.
    """
    if ts.tzinfo is None:
        raise ValueError("classify() requires a timezone-aware datetime (UTC).")

    et = ts.astimezone(_ET)

    # Weekend: Saturday (5) or Sunday (6).
    if et.weekday() >= 5:
        return MarketState.CLOSED

    t = et.time()
    if _REGULAR_OPEN <= t < _REGULAR_CLOSE:
        return MarketState.REGULAR
    if _PREMARKET_OPEN <= t < _REGULAR_OPEN:
        return MarketState.PREMARKET
    if _REGULAR_CLOSE <= t < _AFTERHOURS_CLOSE:
        return MarketState.AFTERHOURS
    # Weekday, outside 04:00-20:00 ET.
    return MarketState.OVERNIGHT
