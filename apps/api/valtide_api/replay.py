"""Replay driver — runs the pipeline over a sequence of snapshots.

This is the primary demo path (BACKEND_PLAN.md §8): feed historical/ scenario
snapshots through the same run_inference used everywhere, warming the Kalman
state forward step by step. Powers both the scripted demo and /api/replay.

The single shared inference core lives here so replay, the (P1) live scheduler,
and one-shot calls all behave identically.
"""

from __future__ import annotations

from collections.abc import Iterable

from valtide_api.models import MarketSnapshot, ValuationResult
from valtide_api.quant_runtime import ModelArtifact, estimate, load_artifact, load_calibrator
from valtide_api.state_store import KalmanState
from valtide_api.validation import Thresholds, validate


def run_inference(
    snapshot: MarketSnapshot,
    prior: KalmanState | None,
    thresholds: Thresholds | None = None,
    artifact: ModelArtifact | None = None,
) -> tuple[ValuationResult, KalmanState]:
    """One step: estimate (NVDAx-first) -> validate -> carry state forward."""
    art = artifact or load_artifact()
    est = estimate(
        snapshot,
        prior.m if prior else None,
        prior.P if prior else None,
        prior.last_ts if prior else None,
        artifact=art,
        calibrator=load_calibrator(),
    )
    result = validate(
        snapshot,
        est,
        thresholds=thresholds,
        model_id=art.deployment_model_id,
        model_version=art.model_version,
    )
    new_state = KalmanState(
        m=est.state_m_after_nvda,
        P=est.state_P_after_nvda,
        last_ts=snapshot.observation_ts,
    )
    return result, new_state


def replay(
    snapshots: Iterable[MarketSnapshot],
    thresholds: Thresholds | None = None,
    artifact: ModelArtifact | None = None,
) -> list[ValuationResult]:
    """Run a full sequence, warming state from the artifact's initial state.

    Returns one ValuationResult per snapshot, in order. Point-in-time correct:
    each step sees only its own snapshot; no future data leaks backward.
    """
    art = artifact or load_artifact()
    state: KalmanState | None = None
    results: list[ValuationResult] = []
    for snap in snapshots:
        result, state = run_inference(snap, state, thresholds=thresholds, artifact=art)
        results.append(result)
    return results
