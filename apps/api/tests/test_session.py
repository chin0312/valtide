"""Session classifier boundary tests. Times chosen in ET, expressed as UTC."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from valtide_api.models import MarketState
from valtide_api.session import classify

_ET = ZoneInfo("America/New_York")


def _et(y, m, d, hh, mm) -> datetime:
    """Build a UTC datetime from an Eastern-time wall clock."""
    return datetime(y, m, d, hh, mm, tzinfo=_ET).astimezone(UTC)


def test_regular_hours():
    # Wednesday 2026-09-23, 10:00 ET -> REGULAR
    assert classify(_et(2026, 9, 23, 10, 0)) == MarketState.REGULAR


def test_premarket():
    assert classify(_et(2026, 9, 23, 5, 0)) == MarketState.PREMARKET


def test_afterhours():
    assert classify(_et(2026, 9, 23, 18, 0)) == MarketState.AFTERHOURS


def test_overnight():
    assert classify(_et(2026, 9, 23, 2, 0)) == MarketState.OVERNIGHT


def test_weekend_closed():
    # Saturday 2026-09-19
    assert classify(_et(2026, 9, 19, 12, 0)) == MarketState.CLOSED


def test_open_boundary_inclusive():
    # 09:30 ET is REGULAR; 09:29 is PREMARKET.
    assert classify(_et(2026, 9, 23, 9, 30)) == MarketState.REGULAR
    assert classify(_et(2026, 9, 23, 9, 29)) == MarketState.PREMARKET


def test_close_boundary():
    # 16:00 ET is AFTERHOURS; 15:59 is REGULAR.
    assert classify(_et(2026, 9, 23, 16, 0)) == MarketState.AFTERHOURS
    assert classify(_et(2026, 9, 23, 15, 59)) == MarketState.REGULAR


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        classify(datetime(2026, 9, 23, 10, 0))
