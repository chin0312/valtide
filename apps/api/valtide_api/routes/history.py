"""GET /api/history/{asset} — warmed operational validation history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from valtide_api.models import ValuationResult
from valtide_api.routes._asset_guard import require_api_asset
from valtide_api.runtime_store import (
    RuntimeStateIntegrityError,
    get_runtime_store,
    runtime_identity_for_asset,
)

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history/{asset}", response_model=list[ValuationResult])
def get_history(
    asset: str,
    limit: int = Query(72, ge=1, le=2016),
) -> list[ValuationResult]:
    """Return successful warmed scheduler results in chronological order.

    This is operational history only. It never runs inference, advances state,
    publishes, or returns scenario/replay/backtest results.
    """
    config = require_api_asset(asset, "runtime", "quant")
    try:
        return get_runtime_store().load_history(
            asset,
            limit=limit,
            expected_identity=runtime_identity_for_asset(config.asset),
            reference_profile=config.reference_profile,
        )
    except RuntimeStateIntegrityError as exc:
        raise HTTPException(status_code=503, detail="history_unavailable") from exc
