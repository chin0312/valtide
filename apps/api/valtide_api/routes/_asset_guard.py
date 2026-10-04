"""Shared asset exposure and capability gate for asset-scoped HTTP routes."""

from fastapi import HTTPException

from valtide_api.assets import (
    AssetConfig,
    AssetConfigurationError,
    UnsupportedAssetError,
    is_supported_asset,
    resolve_asset_config,
)
from valtide_api.quant_runtime import quant_runtime_available


def require_api_asset(asset: str, *capabilities: str) -> AssetConfig:
    if not is_supported_asset(asset):
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")
    try:
        config = resolve_asset_config(asset)
    except UnsupportedAssetError as exc:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported") from exc
    except AssetConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not config.capabilities.api_exposed:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")
    for capability in capabilities:
        if capability == "onchain" and not config.capabilities.onchain:
            raise HTTPException(status_code=503, detail="ONCHAIN_NOT_CONFIGURED")
        if capability == "quant":
            if not config.capabilities.quant:
                raise HTTPException(status_code=503, detail="MODEL_FIT_BLOCKED")
            if not quant_runtime_available(config):
                raise HTTPException(status_code=503, detail="QUANT_ARTIFACT_UNAVAILABLE")
        if capability == "runtime" and not config.capabilities.runtime:
            raise HTTPException(status_code=503, detail="RUNTIME_NOT_READY")
        if capability == "live_data" and not config.capabilities.live_data:
            raise HTTPException(status_code=503, detail="LIVE_DATA_UNAVAILABLE")
        if capability == "historical_data":
            if not config.capabilities.historical_data:
                raise HTTPException(status_code=503, detail="HISTORICAL_DATA_UNAVAILABLE")
    return config
