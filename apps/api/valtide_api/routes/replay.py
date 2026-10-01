"""GET /api/replay/{asset} — point-in-time historical/scenario result.

Runs the scenario (or, later, real historical data) through the replay driver and
returns the result at the requested timestamp — or the full sequence if no
timestamp is given. Point-in-time correct: each step sees only its own snapshot.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from valtide_api.assets import AssetConfigurationError
from valtide_api.data_source import resolve_snapshots
from valtide_api.models import ValuationResult
from valtide_api.replay import replay
from valtide_api.routes._asset_guard import require_api_asset

router = APIRouter(prefix="/api", tags=["replay"])

@router.get("/replay/{asset}", response_model=list[ValuationResult])
def get_replay(
    asset: str,
    response: Response,
    source: str = Query("auto", description="auto | panel | scenario"),
    scenario: str = Query("weekend_divergence"),
    timestamp: str | None = Query(None, description="ISO ts; returns the single matching step"),
) -> list[ValuationResult]:
    require_api_asset(asset, "historical_data", "quant")
    try:
        snapshots, source_label = resolve_snapshots(
            asset=asset,
            source=source,
            scenario=scenario,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="data source not found") from None
    except AssetConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response.headers["X-Valtide-Source"] = source_label

    results = replay(snapshots)

    if timestamp is not None:
        match = [r for r in results if r.timestamp.isoformat().startswith(timestamp[:19])]
        if not match:
            raise HTTPException(status_code=404, detail=f"no step at timestamp '{timestamp}'")
        return match
    return results
