"""Replay driver for the shared backend → quant → validation pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from valtide_api.models import ChallengerEstimate, MarketSnapshot, ValuationResult
from valtide_api.quant_runtime import StateGapError, estimate
from valtide_api.session import classify
from valtide_api.state_store import KalmanState
from valtide_api.validation import Thresholds, validate

_FIVE_MINUTES = timedelta(minutes=5)


def _quant_step(
    snapshot: MarketSnapshot,
    prior: KalmanState | None,
) -> tuple[ChallengerEstimate, KalmanState]:
    """Run one quant-only step and return its carried state."""
    estimate_result = estimate(
        snapshot,
        prior.m if prior else None,
        prior.P if prior else None,
        prior.last_ts if prior else None,
    )
    return estimate_result, KalmanState(
        m=estimate_result.state_m_after_nvda,
        P=estimate_result.state_P_after_nvda,
        last_ts=snapshot.observation_ts,
    )


def _warmup_snapshot(first_snapshot: MarketSnapshot, timestamp: datetime) -> MarketSnapshot:
    """Create an internal no-measurement step before the first real snapshot."""
    anchor = first_snapshot.last_trusted_reference_ts
    return first_snapshot.model_copy(
        update={
            "observation_ts": timestamp,
            "token_price": None,
            "token_volume": None,
            "underlying_reference": None,
            "underlying_reference_ts": None,
            "reference_age_seconds": int((timestamp - anchor).total_seconds()),
            "reference_under_test": None,
            "reference_under_test_ts": None,
            "reference_under_test_age_seconds": None,
            "market_state": classify(timestamp),
            "external_reference": None,
            "source_provenance": {"warmup": "elapsed_time_propagation"},
        }
    )


def _warm_state_to_first_observation(
    first_snapshot: MarketSnapshot,
) -> KalmanState | None:
    """Propagate state to the step immediately before the first real snapshot.

    The quant runtime initializes its state from the trusted reference when no
    prior state exists. Hidden steps then add only elapsed process uncertainty;
    they never become public valuation results.
    """
    anchor = first_snapshot.last_trusted_reference_ts
    first_timestamp = first_snapshot.observation_ts

    if first_timestamp < anchor:
        raise ValueError(
            "first observation must not precede last_trusted_reference_ts: "
            f"{first_timestamp.isoformat()} < {anchor.isoformat()}"
        )
    if first_timestamp == anchor:
        # An existing panel may start on the same timestamp as its trusted
        # underlying bar. There is no elapsed gap to warm, and no state runs
        # backward; the normal cold-start step handles this zero-gap case.
        return None

    elapsed_seconds = (first_timestamp - anchor).total_seconds()
    if elapsed_seconds % _FIVE_MINUTES.total_seconds() != 0:
        raise StateGapError(
            "first observation is not aligned to a canonical 5-minute interval "
            f"from last_trusted_reference_ts: {elapsed_seconds:g} seconds"
        )

    state: KalmanState | None = None
    timestamp = anchor + _FIVE_MINUTES
    while timestamp < first_timestamp:
        _, state = _quant_step(_warmup_snapshot(first_snapshot, timestamp), state)
        timestamp += _FIVE_MINUTES
    return state


def run_inference(
    snapshot: MarketSnapshot,
    prior: KalmanState | None,
    thresholds: Thresholds | None = None,
) -> tuple[ValuationResult, KalmanState]:
    """Run one quant estimate, backend validation, and state carry-forward."""
    est, new_state = _quant_step(snapshot, prior)
    result = validate(snapshot, est, thresholds=thresholds)
    return result, new_state


def replay(
    snapshots: Iterable[MarketSnapshot],
    thresholds: Thresholds | None = None,
) -> list[ValuationResult]:
    """Run actual snapshots with hidden initial elapsed-time propagation."""
    actual_snapshots = list(snapshots)
    if not actual_snapshots:
        return []

    state = _warm_state_to_first_observation(actual_snapshots[0])
    results: list[ValuationResult] = []
    for snap in actual_snapshots:
        result, state = run_inference(snap, state, thresholds=thresholds)
        results.append(result)
    return results
