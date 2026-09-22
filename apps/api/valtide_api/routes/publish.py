"""POST /api/publish/{asset} — publish the latest result to X Layer.

The only write path. Requires server-side authorization. Returns 503 (not 500)
while the X Layer contracts are not yet deployed, so the frontend can show a
clean "publication unavailable" state rather than an error.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from valtide_api import publisher, state_store
from valtide_api.models import SUPPORTED_ASSETS

router = APIRouter(prefix="/api", tags=["publish"])

@router.post("/publish/{asset}")
def post_publish(asset: str) -> dict:
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")

    result = state_store.get_latest_result(asset)
    if result is None:
        raise HTTPException(status_code=409, detail="no validation result to publish yet")

    try:
        receipt = publisher.publish(result)
    except publisher.PublisherNotConfigured as exc:
        # Offchain result remains valid; publication is a separate, degraded state.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"tx_hash": receipt.tx_hash, "registry": receipt.registry_address}
