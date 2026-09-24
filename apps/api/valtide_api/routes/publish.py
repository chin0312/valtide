"""POST /api/publish/{asset} — publish the latest warmed result to X Layer."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from valtide_api import publisher
from valtide_api.config import get_settings
from valtide_api.models import SUPPORTED_ASSETS
from valtide_api.runtime_store import RuntimeStateIntegrityError, get_runtime_store

router = APIRouter(prefix="/api", tags=["publish"])


@router.post("/publish/{asset}")
def post_publish(asset: str) -> dict:
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")

    if not get_settings().publish_enabled:
        raise HTTPException(status_code=503, detail="publication is disabled")

    try:
        record = get_runtime_store().load_runtime(asset)
    except RuntimeStateIntegrityError as exc:
        raise HTTPException(status_code=503, detail="runtime state is invalid") from exc
    result = record.latest_result if record is not None else None
    if result is None:
        raise HTTPException(status_code=409, detail="no validation result to publish yet")

    try:
        receipt = publisher.publish(result, settings=get_settings())
    except publisher.PublisherNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except publisher.PublishabilityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except publisher.ChainPreflightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except publisher.PublicationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return receipt.as_dict()
