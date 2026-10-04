"""Read-only X Layer control-plane status and enforcement diagnostics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from valtide_api import publisher
from valtide_api.routes._asset_guard import require_api_asset

router = APIRouter(prefix="/api", tags=["onchain"])


@router.get("/onchain/{asset}")
def get_onchain(asset: str) -> dict:
    require_api_asset(asset, "onchain", "quant")
    try:
        return {"asset": asset, **publisher.read_control_plane(asset=asset)}
    except publisher.PublisherNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except publisher.ChainPreflightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/onchain/{asset}/enforcement")
def get_onchain_enforcement(asset: str) -> dict:
    require_api_asset(asset, "onchain", "quant")
    try:
        return {"asset": asset, **publisher.check_demo_vault_enforcement(asset=asset)}
    except publisher.PublisherNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except publisher.ChainPreflightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
