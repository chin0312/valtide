"""Canonical production asset registry.

This module owns the backend's asset-specific behavioral configuration.  It is
deliberately small: registering an entry here does not by itself make an asset
live, publishable, or frontend-visible.  Those capabilities still require the
corresponding explicit deployment/runtime configuration.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from valtide_api.config import Settings


class AssetRegistryError(ValueError):
    """Base error for invalid or unsupported asset configuration."""


class UnsupportedAssetError(AssetRegistryError):
    """Raised when a caller requests an asset outside the production registry."""


class AssetConfigurationError(AssetRegistryError):
    """Raised when a registered asset cannot be resolved safely."""


@dataclass(frozen=True)
class AssetConfig:
    """Immutable behavioral configuration for one registered asset."""

    asset: str
    underlying_symbol: str
    token_source: str
    underlying_source: str
    okx_chain_index: str | None
    token_address: str | None
    reference_under_test_source: str
    reference_under_test_instrument: str
    # The Registry reference identity is intentionally distinct from the vendor
    # instrument name.  It is the existing public identity hashed in the
    # deployment manifest and must not be changed by this refactor.
    xlayer_reference_name: str
    quant_model_id: str
    quant_model_version: str
    historical_panel_path: Path | None
    xlayer_asset_id: str | None
    xlayer_reference_id: str | None
    demo_vault_address: str | None
    production_enabled: bool


_NVDA_CONFIG = AssetConfig(
    asset="NVDAx",
    underlying_symbol="NVDA",
    token_source="okx_onchainos",
    underlying_source="alpaca",
    okx_chain_index=None,
    token_address=None,
    reference_under_test_source="okx_xperp_index",
    reference_under_test_instrument="NVDA-USD",
    xlayer_reference_name="OKX_NVDA_USD_INDEX",
    quant_model_id="P1a-C",
    quant_model_version="0.2.0",
    historical_panel_path=None,
    xlayer_asset_id=None,
    xlayer_reference_id=None,
    demo_vault_address=None,
    production_enabled=True,
)

# Keep this mapping private and immutable.  A future asset must be added only
# with an explicit review of its behavioral, quant, and deployment bindings.
_ASSET_REGISTRY: Mapping[str, AssetConfig] = MappingProxyType(
    {
        _NVDA_CONFIG.asset: _NVDA_CONFIG,
    }
)


def supported_asset_names() -> tuple[str, ...]:
    """Return registered production asset names in deterministic order."""

    return tuple(
        config.asset
        for config in _ASSET_REGISTRY.values()
        if config.production_enabled
    )


def production_asset_configs() -> tuple[AssetConfig, ...]:
    """Return immutable configs for currently production-enabled assets."""

    return tuple(
        config
        for config in _ASSET_REGISTRY.values()
        if config.production_enabled
    )


def resolve_asset_config(asset: str, settings: Settings | None = None) -> AssetConfig:
    """Resolve one production asset, including its existing env-backed values.

    Unknown assets fail before any source, quant artifact, SQLite state, or
    deployment metadata is selected.  The NVDAx environment names remain the
    compatibility boundary for the only currently supported production asset.
    """

    config = _ASSET_REGISTRY.get(asset)
    if config is None or not config.production_enabled:
        raise UnsupportedAssetError(f"asset '{asset}' not supported")

    if settings is None:
        from valtide_api.config import get_settings

        settings = get_settings()

    if config.asset == "NVDAx":
        chain_index = str(getattr(settings, "okx_nvdax_chain_index", "") or "").strip()
        token_address = str(getattr(settings, "okx_nvdax_token_address", "") or "").strip()
        if bool(chain_index) != bool(token_address):
            raise AssetConfigurationError(
                "OKX_NVDAX_CHAIN_INDEX and OKX_NVDAX_TOKEN_ADDRESS must be configured together"
            )
        historical_path = getattr(settings, "resolved_historical_panel_path", None)
        reference_instrument = str(
            getattr(
                settings,
                "okx_xperp_index_id",
                config.reference_under_test_instrument,
            )
            or config.reference_under_test_instrument
        ).strip()
        if not reference_instrument:
            raise AssetConfigurationError(
                "OKX X-Perp reference instrument must be configured for NVDAx"
            )
        return replace(
            config,
            okx_chain_index=chain_index or None,
            token_address=token_address or None,
            historical_panel_path=historical_path,
            reference_under_test_instrument=reference_instrument,
        )

    raise AssetConfigurationError(f"no resolver is defined for asset '{asset}'")


def is_supported_asset(asset: str) -> bool:
    """Return whether ``asset`` is explicitly enabled for production."""

    return asset in supported_asset_names()


__all__ = [
    "AssetConfig",
    "AssetConfigurationError",
    "AssetRegistryError",
    "UnsupportedAssetError",
    "is_supported_asset",
    "production_asset_configs",
    "resolve_asset_config",
    "supported_asset_names",
]
