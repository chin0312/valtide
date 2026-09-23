"""GET /api/assets — supported assets and data availability.

The packaged P1a-C artifacts are the default model source for the supported MVP
asset; live data availability is reported by the valuation routes.
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
            model_available=True,
        )
    ]
