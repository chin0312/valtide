"""Read-only X Layer control-plane status and enforcement diagnostics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from valtide_api import publisher
from valtide_api.models import SUPPORTED_ASSETS

router = APIRouter(prefix="/api", tags=["onchain"])


@router.get("/onchain/{asset}")
def get_onchain(asset: str) -> dict:
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")
    try:
        return publisher.read_control_plane()
    except publisher.PublisherNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except publisher.ChainPreflightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/onchain/{asset}/enforcement")
def get_onchain_enforcement(asset: str) -> dict:
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")
    try:
        return publisher.check_demo_vault_enforcement()
    except publisher.PublisherNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except publisher.ChainPreflightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
