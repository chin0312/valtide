"""GET /api/valuation/{asset} — latest cached validation result."""

from fastapi import APIRouter, HTTPException

from valtide_api.live import LiveDataUnavailable, run_live_valuation
from valtide_api.models import ValuationResult
from valtide_api.routes._asset_guard import require_api_asset
from valtide_api.runtime_store import (
    RuntimeStateIntegrityError,
    get_runtime_store,
    runtime_identity_for_asset,
)

router = APIRouter(prefix="/api", tags=["valuation"])


@router.get("/valuation/{asset}", response_model=ValuationResult)
def get_valuation(asset: str) -> ValuationResult:
    """Latest cached validation result. Reads only — never advances the filter.

    Serves only a result computed by replay or the scheduler. A cold cache is an
    explicit data-unavailable condition rather than a fabricated valuation.
    """
    config = require_api_asset(asset, "runtime", "quant")
    try:
        record = get_runtime_store().load_runtime(
            asset, expected_identity=runtime_identity_for_asset(config.asset)
        )
    except RuntimeStateIntegrityError as exc:
        raise HTTPException(status_code=503, detail="runtime_state_unavailable") from exc
    if record is None or record.latest_result is None:
        raise HTTPException(status_code=503, detail="data_unavailable")
    return record.latest_result


@router.get("/valuation/{asset}/live", response_model=ValuationResult)
def get_live_valuation(asset: str) -> ValuationResult:
    """Assemble a snapshot from live sources and run one inference on demand.

    Compute-only; does not mutate the cache. Returns 503 if a required live
    input is unavailable (e.g. OKX OnchainOS or Alpaca data is unreachable).
    """
    require_api_asset(asset, "live_data", "quant")
    try:
        return run_live_valuation(asset=asset)
    except LiveDataUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
