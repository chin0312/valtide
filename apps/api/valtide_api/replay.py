"""Replay driver for the shared backend → quant → validation pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from valtide_api.clock import FIVE_MINUTES, require_canonical_5m
from valtide_api.models import ChallengerEstimate, MarketSnapshot, ValuationResult
from valtide_api.quant_runtime import StateGapError, estimate
from valtide_api.session import classify
from valtide_api.state_store import KalmanState
from valtide_api.validation import Thresholds, validate


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


def _warmup_snapshot(
    template: MarketSnapshot,
    timestamp: datetime,
    *,
    anchor_reference: float | None = None,
    anchor_ts: datetime | None = None,
) -> MarketSnapshot:
    """Create an internal no-measurement step before the first real snapshot."""
    anchor = anchor_ts or template.last_trusted_reference_ts
    reference = (
        anchor_reference if anchor_reference is not None else template.last_trusted_reference
    )
    return template.model_copy(
        update={
            "observation_ts": timestamp,
            "token_price": None,
            "token_volume": None,
            "underlying_reference": None,
            "underlying_reference_ts": None,
            "last_trusted_reference": reference,
            "last_trusted_reference_ts": anchor,
            "reference_age_seconds": max(0, int((timestamp - anchor).total_seconds())),
            "reference_under_test": None,
            "reference_under_test_ts": None,
            "reference_under_test_age_seconds": None,
            "market_state": classify(timestamp),
            "external_reference": None,
            "source_provenance": {"warmup": "elapsed_time_propagation"},
        }
    )


def advance_without_measurements(
    state: KalmanState,
    from_ts: datetime,
    to_ts: datetime,
    template: MarketSnapshot,
    *,
    anchor_reference: float | None = None,
    anchor_ts: datetime | None = None,
) -> tuple[KalmanState, int]:
    """Advance a carried state over missing canonical intervals only."""
    try:
        start = require_canonical_5m(from_ts, "from_ts")
        end = require_canonical_5m(to_ts, "to_ts")
    except ValueError as exc:
        raise StateGapError(str(exc)) from exc
    if state.last_ts != start:
        raise StateGapError(
            f"state timestamp {state.last_ts!s} does not match propagation start {start!s}"
        )
    delta_seconds = (end - start).total_seconds()
    if delta_seconds < 0 or delta_seconds % FIVE_MINUTES.total_seconds() != 0:
        raise StateGapError("state propagation requires an ordered canonical 5-minute interval")

    steps = 0
    timestamp = start + FIVE_MINUTES
    while timestamp < end:
        _, state = _quant_step(
            _warmup_snapshot(
                template,
                timestamp,
                anchor_reference=anchor_reference,
                anchor_ts=anchor_ts,
            ),
            state,
        )
        steps += 1
        timestamp += FIVE_MINUTES
    return state, steps


def _warm_state_to_first_observation_with_count(
    first_snapshot: MarketSnapshot,
) -> tuple[KalmanState | None, int]:
    """Propagate state to the step immediately before the first real snapshot.

    The quant runtime initializes its state from the trusted reference when no
    prior state exists. Hidden steps then add only elapsed process uncertainty;
    they never become public valuation results.
    """
    anchor = first_snapshot.last_trusted_reference_ts
    first_timestamp = first_snapshot.observation_ts

    try:
        anchor = require_canonical_5m(anchor, "last_trusted_reference_ts")
        first_timestamp = require_canonical_5m(first_timestamp, "observation_ts")
    except ValueError as exc:
        raise StateGapError(str(exc)) from exc

    if first_timestamp < anchor:
        raise ValueError(
            "first observation must not precede last_trusted_reference_ts: "
            f"{first_timestamp.isoformat()} < {anchor.isoformat()}"
        )
    if first_timestamp == anchor:
        # An existing panel may start on the same timestamp as its trusted
        # underlying bar. There is no elapsed gap to warm, and no state runs
        # backward; the normal cold-start step handles this zero-gap case.
        return None, 0

    elapsed_seconds = (first_timestamp - anchor).total_seconds()
    if elapsed_seconds % FIVE_MINUTES.total_seconds() != 0:
        raise StateGapError(
            "first observation is not aligned to a canonical 5-minute interval "
            f"from last_trusted_reference_ts: {elapsed_seconds:g} seconds"
        )

    state: KalmanState | None = None
    timestamp = anchor + FIVE_MINUTES
    steps = 0
    while timestamp < first_timestamp:
        _, state = _quant_step(_warmup_snapshot(first_snapshot, timestamp), state)
        steps += 1
        timestamp += FIVE_MINUTES
    return state, steps


def _warm_state_to_first_observation(first_snapshot: MarketSnapshot) -> KalmanState | None:
    """Compatibility wrapper returning only the carried state."""
    state, _ = _warm_state_to_first_observation_with_count(first_snapshot)
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
    previous_ts: datetime | None = None
    results: list[ValuationResult] = []
    for snap in actual_snapshots:
        try:
            current_ts = require_canonical_5m(snap.observation_ts, "observation_ts")
        except ValueError as exc:
            raise StateGapError(str(exc)) from exc
        if previous_ts is not None and (current_ts - previous_ts).total_seconds() != 300:
            raise StateGapError("replay snapshots must advance by exactly 5 minutes")
        result, state = run_inference(snap, state, thresholds=thresholds)
        results.append(result)
        previous_ts = current_ts
    return results
