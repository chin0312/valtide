"""Canonical UTC five-minute clock tests."""

from datetime import UTC, datetime

import pytest

from valtide_api.clock import canonical_5m_boundary, next_5m_boundary, require_canonical_5m


def test_clock_floors_to_utc_boundary_without_rounding_future():
    value = datetime(2026, 9, 19, 14, 7, 42, 123000, tzinfo=UTC)

    assert canonical_5m_boundary(value) == datetime(2026, 9, 19, 14, 5, tzinfo=UTC)
    assert next_5m_boundary(value) == datetime(2026, 9, 19, 14, 10, tzinfo=UTC)


def test_require_canonical_normalizes_offsets_and_rejects_noncanonical_values():
    canonical = require_canonical_5m(
        datetime(2026, 9, 19, 22, 0, tzinfo=UTC)
    )
    assert canonical == datetime(2026, 9, 19, 22, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="canonical 5-minute"):
        require_canonical_5m(datetime(2026, 9, 19, 14, 1, tzinfo=UTC))

    with pytest.raises(ValueError, match="timezone-aware"):
        require_canonical_5m(datetime(2026, 9, 19, 14, 0))
