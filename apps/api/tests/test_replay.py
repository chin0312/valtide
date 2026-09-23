"""Initial elapsed-time warm-up tests for sequential replay."""

from datetime import UTC, datetime, timedelta

import pytest

from valtide_api.models import MarketSnapshot
from valtide_api.quant_runtime import StateGapError
from valtide_api.replay import _warm_state_to_first_observation, replay
from valtide_api.session import classify

_ANCHOR = datetime(2026, 9, 21, 13, 0, tzinfo=UTC)


def _snapshot(
    timestamp: datetime,
    *,
    token_price: float | None = 185.1,
    reference_under_test: float | None = 190.0,
) -> MarketSnapshot:
    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=timestamp,
        token_price=token_price,
        token_volume=50_000.0 if token_price is not None else None,
        underlying_reference=None,
        underlying_reference_ts=None,
        last_trusted_reference=180.0,
        last_trusted_reference_ts=_ANCHOR,
        reference_age_seconds=int((timestamp - _ANCHOR).total_seconds()),
        reference_under_test=reference_under_test,
        reference_under_test_source="okx_xperp_index",
        reference_under_test_ts=(timestamp if reference_under_test is not None else None),
        reference_under_test_age_seconds=(
            0 if reference_under_test is not None else None
        ),
        market_state=classify(timestamp),
        source_provenance={"test": "replay_warmup"},
    )


def test_elapsed_warmup_matches_explicit_five_minute_sequence():
    first_timestamp = _ANCHOR + timedelta(hours=1)
    first = _snapshot(first_timestamp)

    automatic = replay([first])
    hidden = [
        _snapshot(
            _ANCHOR + timedelta(minutes=5 * index),
            token_price=None,
            reference_under_test=None,
        )
        for index in range(1, 12)
    ]
    explicit = replay([*hidden, first])

    assert len(hidden) == 11
    assert automatic[0] == explicit[-1]


def test_warmup_rows_are_not_public_replay_results():
    snapshots = [_snapshot(_ANCHOR + timedelta(hours=1, minutes=5 * i)) for i in range(4)]

    assert len(replay(snapshots)) == 4


def test_no_extra_warmup_for_one_five_minute_gap():
    first = _snapshot(_ANCHOR + timedelta(minutes=5))

    assert _warm_state_to_first_observation(first) is None
    assert len(replay([first])) == 1


def test_equal_anchor_is_explicit_zero_gap_start():
    first = _snapshot(_ANCHOR)

    assert _warm_state_to_first_observation(first) is None
    assert len(replay([first])) == 1


def test_earlier_first_observation_is_rejected():
    first = _snapshot(_ANCHOR - timedelta(minutes=5))

    with pytest.raises(ValueError, match="must not precede"):
        replay([first])


def test_noncanonical_initial_gap_is_rejected():
    first = _snapshot(_ANCHOR + timedelta(minutes=7))

    with pytest.raises(StateGapError, match="canonical 5-minute"):
        replay([first])
