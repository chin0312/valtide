"""GET /api/backtest/{asset} — scenario-derived evidence counts.

Point-accuracy and coverage metrics require a point-in-time historical evaluator
and are intentionally left null by this scenario route.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from valtide_api.models import SUPPORTED_ASSETS, EvidenceState
from valtide_api.replay import replay
from valtide_api.scenario import load_scenario

router = APIRouter(prefix="/api", tags=["backtest"])

class BacktestMetrics(BaseModel):
    asset: str
    source: str  # "scenario" now; "historical" once real data is wired
    n_observations: int
    evidence_state_counts: dict[str, int]
    # Not computed by the scenario-only route.
    mae: float | None = None
    rmse: float | None = None
    interval_coverage: float | None = None
    note: str


@router.get("/backtest/{asset}", response_model=BacktestMetrics)
def get_backtest(asset: str) -> BacktestMetrics:
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")

    results = replay(load_scenario())
    counts = {s.value: 0 for s in EvidenceState}
    for r in results:
        counts[r.evidence_state.value] += 1

    return BacktestMetrics(
        asset=asset,
        source="scenario",
        n_observations=len(results),
        evidence_state_counts=counts,
        note="Scenario-derived counts only; point-accuracy metrics require "
        "point-in-time historical evaluation.",
    )
