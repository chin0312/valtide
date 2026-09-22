"""GET /api/assets — supported assets and data availability.

Phase 1: static list. Phase 2: reflects real adapter/model availability.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["assets"])


class AssetInfo(BaseModel):
    asset: str
    token_source: str
    underlying_source: str
    model_available: bool


@router.get("/assets", response_model=list[AssetInfo])
def list_assets() -> list[AssetInfo]:
    return [
        AssetInfo(
            asset="NVDAx",
            token_source="okx_onchainos",
            underlying_source="alpaca",
            model_available=False,  # flips true once a real artifact is loaded
        )
    ]
