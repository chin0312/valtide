"""Canonical UTC clock helpers for the sequential P1a-C runtime."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

FIVE_MINUTES = timedelta(minutes=5)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("canonical clock requires a timezone-aware datetime")
    return value.astimezone(UTC)


def canonical_5m_boundary(now_utc: datetime) -> datetime:
    """Floor an aware timestamp to its canonical five-minute UTC boundary."""
    now = _as_utc(now_utc)
    return now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)


def is_canonical_5m(value: datetime) -> bool:
    """Return whether a timestamp is an aware exact five-minute UTC boundary."""
    if value.tzinfo is None:
        return False
    utc = value.astimezone(UTC)
    return utc.minute % 5 == 0 and utc.second == 0 and utc.microsecond == 0


def next_5m_boundary(value: datetime) -> datetime:
    """Return the next canonical boundary after an aware timestamp."""
    return canonical_5m_boundary(value) + FIVE_MINUTES


def require_canonical_5m(value: datetime, label: str = "timestamp") -> datetime:
    """Normalize and validate a timestamp without silently rounding it."""
    utc = _as_utc(value)
    if not is_canonical_5m(utc):
        raise ValueError(f"{label} must use a canonical 5-minute UTC boundary")
    return utc


__all__ = [
    "FIVE_MINUTES",
    "canonical_5m_boundary",
    "is_canonical_5m",
    "next_5m_boundary",
    "require_canonical_5m",
]
