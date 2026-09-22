"""Quant runtime — runs ONE Kalman step from pre-fitted parameters.

Python port of the inner loop of James's kalman_filter_p0 (R/kalman_p0.R). This
is the ONLY place model math lives on the backend, and it only *runs* fitted
parameters — it never fits them.

Model (log-price space):
    m_t      = m_{t-1} + eta,     eta  ~ N(0, Q)
    ln(NVDA) = m_t + eps_nvda,    eps  ~ N(0, R_nvda)
    ln(NVDAx)= m_t + eps_nvdax,   eps  ~ N(0, R_nvdax)

Update order (BACKEND_PLAN.md §3 — keeps the challenger independent of NVDA):
    1. predict:            m_pred = m_prev;  P_pred = P_prev + Q
    2. assimilate NVDAx  -> (m1, P1)  == the independent challenger
    3. read off fair value + interval from (m1, P1)
    4. assimilate NVDA (if present) -> (m2, P2)  carried into the next step

Sequential scalar updates are mathematically equivalent to James's joint update
when both prices are present, but expose the NVDAx-only posterior we validate.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from valtide_api.config import get_settings
from valtide_api.models import ChallengerEstimate, MarketSnapshot

# 90% two-sided Gaussian quantile (matches James's 1.644854 in kalman_p0.R).
_Z90 = 1.644854

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent  # apps/api/


@dataclass(frozen=True)
class ModelArtifact:
    model_id: str
    model_version: str
    Q: float
    R_nvda: float
    R_nvdax: float
    m0: float
    P0: float
    coverage_target: float
    calibrator: str


@lru_cache
def load_artifact(path: str | None = None) -> ModelArtifact:
    """Load the fitted-parameter artifact once. Defaults to settings path."""
    artifact_path = Path(path or get_settings().model_artifact_path)
    if not artifact_path.is_absolute():
        artifact_path = _PACKAGE_ROOT / artifact_path
    data = json.loads(artifact_path.read_text())
    return ModelArtifact(
        model_id=data["modelId"],
        model_version=data["modelVersion"],
        Q=float(data["params"]["Q"]),
        R_nvda=float(data["params"]["R_nvda"]),
        R_nvdax=float(data["params"]["R_nvdax"]),
        m0=float(data["initialState"]["m0"]),
        P0=float(data["initialState"]["P0"]),
        coverage_target=float(data.get("intervalCoverageTarget", 0.90)),
        calibrator=data.get("calibrator", "gaussian"),
    )


def _kalman_update(m_pred: float, P_pred: float, obs: float, R: float) -> tuple[float, float]:
    """One scalar Kalman measurement update (observation matrix H = 1)."""
    S = P_pred + R
    K = P_pred / S
    m = m_pred + K * (obs - m_pred)
    P = max((1.0 - K) * P_pred, 1e-12)
    return m, P


def estimate(
    snapshot: MarketSnapshot,
    prior_m: float,
    prior_P: float,
    artifact: ModelArtifact | None = None,
) -> ChallengerEstimate:
    """Run one filter step and return the NVDAx-only challenger + carried state."""
    art = artifact or load_artifact()

    # 1. Predict.
    m_pred = prior_m
    P_pred = prior_P + art.Q

    # 2. Assimilate NVDAx only -> the independent challenger.
    m1, P1 = _kalman_update(m_pred, P_pred, math.log(snapshot.token_price), art.R_nvdax)

    # 3. Read off fair value + interval from the NVDAx-only posterior.
    sd1 = math.sqrt(P1)
    fair_value = math.exp(m1)
    lower = math.exp(m1 - _Z90 * sd1)
    upper = math.exp(m1 + _Z90 * sd1)

    # 4. Then fold in NVDA if present, to carry state into the next step.
    if snapshot.underlying_reference is not None and snapshot.underlying_reference > 0:
        m2, P2 = _kalman_update(m1, P1, math.log(snapshot.underlying_reference), art.R_nvda)
    else:
        m2, P2 = m1, P1

    return ChallengerEstimate(
        fair_value=fair_value,
        lower_bound=lower,
        upper_bound=upper,
        state_m=m1,
        state_sd_log=sd1,
        coverage_target=art.coverage_target,
        state_m_after_nvda=m2,
        state_P_after_nvda=P2,
    )
