"""Adapter from backend snapshots to the trained P1a-C quant runtime.

The model implementation and artifacts live in ``valtide_quant_service`` (PR #3).
This module only translates the backend's canonical objects and exposes the
challenger state needed by the validation engine.
"""

from __future__ import annotations

import math
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from valtide_quant_service.artifacts import P1aArtifact, load_p1a
from valtide_quant_service.calibration import P1aCCalibrator
from valtide_quant_service.runtime import FilterState, P1aCRuntime, StateGapError
from valtide_quant_service.schemas import MarketSnapshot as QuantMarketSnapshot

from valtide_api.config import get_settings
from valtide_api.models import ChallengerEstimate, MarketSnapshot

ModelArtifact = P1aArtifact


def _configured_path(value: str, filename: str):
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / path
        return path
    return files("valtide_quant_service").joinpath("model_artifacts", filename)


@lru_cache
def load_artifact(path: str | None = None) -> ModelArtifact:
    """Load the exact trained P1a artifact packaged by the quant service."""
    configured = path if path is not None else get_settings().model_artifact_path
    return load_p1a(_configured_path(configured, "p1a_runtime.json"))


@lru_cache
def load_calibrator(path: str | None = None) -> P1aCCalibrator:
    """Load the P1a-C empirical interval calibrator packaged by the quant service."""
    configured = path if path is not None else get_settings().calibrator_artifact_path
    return P1aCCalibrator(_configured_path(configured, "p1a_c_calibrator.json"))


def estimate(
    snapshot: MarketSnapshot,
    prior_m: float | None = None,
    prior_P: float | None = None,
    prior_ts: datetime | None = None,
    artifact: ModelArtifact | None = None,
    calibrator: P1aCCalibrator | None = None,
) -> ChallengerEstimate:
    """Run one P1a-C step while preserving its causal update order and calibration."""
    art = artifact or load_artifact()
    cal = calibrator or load_calibrator()
    state = None
    if prior_m is not None and prior_P is not None:
        state = FilterState(prior_m, prior_P, prior_ts)

    runtime = P1aCRuntime(art, cal, state)
    quant_snapshot = QuantMarketSnapshot(
        asset=snapshot.asset,
        timestamp=snapshot.observation_ts,
        quant_session=snapshot.market_state.value,
        token_price=snapshot.token_price,
        current_underlying_price=snapshot.underlying_reference,
        last_trusted_reference=snapshot.last_trusted_reference,
        last_trusted_reference_timestamp=snapshot.last_trusted_reference_ts,
        external_constructed_reference=snapshot.external_reference,
    )
    result = runtime.step(quant_snapshot)
    carried = runtime.state
    if carried is None:  # pragma: no cover - runtime.step always creates state
        raise RuntimeError("quant runtime did not return a carried state")

    return ChallengerEstimate(
        fair_value=result.fair_value,
        lower_bound=result.primary_lower,
        upper_bound=result.primary_upper,
        state_m=result.challenger_m_log,
        state_sd_log=math.sqrt(result.challenger_P_log),
        reference_predictive_sd_log=result.reference_predictive_sd_log,
        coverage_target=cal.level,
        interval_calibration_type=result.calibration.calibration_type,
        interval_calibration_source=result.calibration.source,
        state_m_after_nvda=carried.m,
        state_P_after_nvda=carried.P,
    )


__all__ = [
    "ModelArtifact",
    "StateGapError",
    "estimate",
    "load_artifact",
    "load_calibrator",
]
