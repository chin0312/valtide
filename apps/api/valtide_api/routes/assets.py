"""GET /api/assets — supported assets and data availability.

The packaged P1a-C artifacts are the default model source for the supported MVP
asset; live data availability is reported by the valuation routes.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from valtide_api.assets import production_asset_configs
from valtide_api.quant_runtime import quant_runtime_available

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
            asset=config.asset,
            token_source=config.token_source,
            underlying_source=config.underlying_source,
            model_available=quant_runtime_available(config),
        )
        for config in production_asset_configs()
    ]
