"""GET /api/backtest/{asset} — scenario counts or historical metrics."""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from valtide_api.data_source import resolve_snapshots
from valtide_api.models import SUPPORTED_ASSETS, EvidenceState
from valtide_api.replay import replay

router = APIRouter(prefix="/api", tags=["backtest"])

class BacktestMetrics(BaseModel):
    asset: str
    source: str
    n_observations: int
    evidence_state_counts: dict[str, int]
    n_evaluable: int
    mae: float | None = None
    rmse: float | None = None
    interval_coverage: float | None = None
    note: str


@router.get("/backtest/{asset}", response_model=BacktestMetrics)
def get_backtest(
    asset: str, source: str = "scenario", scenario: str = "weekend_divergence"
) -> BacktestMetrics:
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")

    try:
        snapshots, source_label = resolve_snapshots(source=source, scenario=scenario)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="data source not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results = replay(snapshots)
    counts = {s.value: 0 for s in EvidenceState}
    for r in results:
        counts[r.evidence_state.value] += 1

    evaluable = [
        (snapshot, result)
        for snapshot, result in zip(snapshots, results, strict=True)
        if source_label == "historical_panel" and snapshot.underlying_reference is not None
    ]
    errors = [
        result.valtide_fair_value - snapshot.underlying_reference
        for snapshot, result in evaluable
    ]
    mae = sum(abs(error) for error in errors) / len(errors) if errors else None
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors)) if errors else None
    interval_coverage = (
        sum(
            result.fair_value_lower <= snapshot.underlying_reference <= result.fair_value_upper
            for snapshot, result in evaluable
        )
        / len(evaluable)
        if evaluable
        else None
    )

    if source_label == "scenario":
        note = (
            "Scenario-derived counts only; metrics are intentionally null because "
            "the scenario has no empirical ground truth."
        )
        output_source = "scenario"
    else:
        note = (
            "Metrics use only rows with a contemporaneous trusted NVDA observation; "
            "they are historical diagnostics, not production guarantees."
        )
        output_source = "historical"

    return BacktestMetrics(
        asset=asset,
        source=output_source,
        n_observations=len(results),
        evidence_state_counts=counts,
        n_evaluable=len(evaluable),
        mae=mae,
        rmse=rmse,
        interval_coverage=interval_coverage,
        note=note,
    )
