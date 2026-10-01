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
        if not getattr(config.capabilities, capability):
            raise HTTPException(
                status_code=503, detail=f"{capability} is unavailable for asset '{asset}'"
            )
        if capability == "quant" and not quant_runtime_available(config):
            raise HTTPException(
                status_code=503, detail=f"quant runtime is unavailable for asset '{asset}'"
            )
    return config
