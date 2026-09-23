"""Replay driver for the shared backend → quant → validation pipeline."""

from __future__ import annotations

from collections.abc import Iterable

from valtide_api.models import MarketSnapshot, ValuationResult
from valtide_api.quant_runtime import estimate
from valtide_api.state_store import KalmanState
from valtide_api.validation import Thresholds, validate


def run_inference(
    snapshot: MarketSnapshot,
    prior: KalmanState | None,
    thresholds: Thresholds | None = None,
) -> tuple[ValuationResult, KalmanState]:
    """Run one quant estimate, backend validation, and state carry-forward."""
    est = estimate(
        snapshot,
        prior.m if prior else None,
        prior.P if prior else None,
        prior.last_ts if prior else None,
    )
    result = validate(snapshot, est, thresholds=thresholds)
    new_state = KalmanState(
        m=est.state_m_after_nvda,
        P=est.state_P_after_nvda,
        last_ts=snapshot.observation_ts,
    )
    return result, new_state


def replay(
    snapshots: Iterable[MarketSnapshot],
    thresholds: Thresholds | None = None,
) -> list[ValuationResult]:
    """Run a point-in-time sequence with one carried P1a-C state."""
    state: KalmanState | None = None
    results: list[ValuationResult] = []
    for snap in snapshots:
        result, state = run_inference(snap, state, thresholds=thresholds)
        results.append(result)
    return results
