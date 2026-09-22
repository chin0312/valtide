"""GET /api/valuation/{asset} — latest cached validation result.

Phase 1: serves a mock result so the frontend is unblocked.
Later phases: reads the latest cached ValuationResult from state_store. This
route NEVER advances the Kalman filter — reads only.
"""

from fastapi import APIRouter, HTTPException

from valtide_api import state_store
from valtide_api.live import LiveDataUnavailable, run_live_valuation
from valtide_api.mock_data import MOCK_VALUATION
from valtide_api.models import SUPPORTED_ASSETS, ValuationResult

router = APIRouter(prefix="/api", tags=["valuation"])


@router.get("/valuation/{asset}", response_model=ValuationResult)
def get_valuation(asset: str) -> ValuationResult:
    """Latest cached validation result. Reads only — never advances the filter.

    Serves the real cached result once the replay driver / scheduler has produced
    one; falls back to the mock so the frontend always has a stable shape to
    render during development.
    """
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")
    cached = state_store.get_latest_result(asset)
    return cached if cached is not None else MOCK_VALUATION


@router.get("/valuation/{asset}/live", response_model=ValuationResult)
def get_live_valuation(asset: str) -> ValuationResult:
    """Assemble a snapshot from live sources and run one inference on demand.

    Compute-only; does not mutate the cache. Returns 503 if a required live
    input is unavailable (e.g. Alpaca key missing, DexScreener unreachable).
    """
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")
    try:
        return run_live_valuation()
    except LiveDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
