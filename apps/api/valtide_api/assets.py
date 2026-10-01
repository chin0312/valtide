"""Canonical production asset registry.

This module owns the backend's asset-specific behavioral configuration.  It is
deliberately small: registering an entry here does not by itself make an asset
live, publishable, or frontend-visible.  Those capabilities still require the
corresponding explicit deployment/runtime configuration.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
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
class AssetCapabilities:
    live_data: bool = False
    historical_data: bool = False
    quant: bool = False
    runtime: bool = False
    onchain: bool = False
    api_exposed: bool = False


@dataclass(frozen=True)
class AssetConfig:
    """Immutable behavioral configuration for one registered asset."""

    asset: str
    underlying_symbol: str
    token_source: str
    underlying_source: str
    token_market_key: str
    okx_chain_index: str | None
    token_address: str | None
    allow_token_discovery: bool
    reference_under_test_source: str
    reference_under_test_instrument: str
    # The Registry reference identity is intentionally distinct from the vendor
    # instrument name.  It is the existing public identity hashed in the
    # deployment manifest and must not be changed by this refactor.
    xlayer_reference_name: str
    quant_runtime_key: str
    historical_panel_key: str
    capabilities: AssetCapabilities
    production_enabled: bool


_NVDA_CONFIG = AssetConfig(
    asset="NVDAx",
    underlying_symbol="NVDA",
    token_source="okx_onchainos",
    underlying_source="alpaca",
    token_market_key="okx_onchainos",
    okx_chain_index=None,
    token_address=None,
    allow_token_discovery=True,
    reference_under_test_source="okx_xperp_index",
    reference_under_test_instrument="NVDA-USD",
    xlayer_reference_name="OKX_NVDA_USD_INDEX",
    quant_runtime_key="nvdax_p1ac_default",
    historical_panel_key="nvdax_panel",
    capabilities=AssetCapabilities(True, True, True, True, True, True),
    production_enabled=True,
)

# Keep this mapping private and immutable.  A future asset must be added only
# with an explicit review of its behavioral, quant, and deployment bindings.
_ASSET_REGISTRY: Mapping[str, AssetConfig] = MappingProxyType(
    {
        _NVDA_CONFIG.asset: _NVDA_CONFIG,
    }
)

_HISTORICAL_PANEL_PATHS: Mapping[str, tuple[str, Callable[[Settings], Path]]] = (
    MappingProxyType({
        "nvdax_panel": ("NVDAx", lambda settings: settings.resolved_historical_panel_path),
    })
)


def supported_asset_names() -> tuple[str, ...]:
    """Return registered production asset names in deterministic order."""

    return tuple(
        config.asset
        for config in _ASSET_REGISTRY.values()
        if config.production_enabled and config.capabilities.api_exposed
    )


def production_asset_configs() -> tuple[AssetConfig, ...]:
    """Return immutable configs for currently production-enabled assets."""

    return tuple(
        config
        for config in _ASSET_REGISTRY.values()
        if config.production_enabled and config.capabilities.api_exposed
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
            reference_under_test_instrument=reference_instrument,
        )

    if bool(config.okx_chain_index) != bool(config.token_address):
        raise AssetConfigurationError("token chain index and address must be configured together")
    if not config.allow_token_discovery and not config.okx_chain_index:
        raise AssetConfigurationError(f"token deployment must be pinned for '{asset}'")
    return config


def is_supported_asset(asset: str) -> bool:
    """Return whether ``asset`` is explicitly enabled for production."""

    return asset in supported_asset_names()


def resolve_historical_panel_path(config: AssetConfig, settings: Settings | None = None) -> Path:
    """Resolve an explicitly registered panel key, never a global fallback."""
    if not config.capabilities.historical_data:
        raise AssetConfigurationError(f"historical data is unavailable for '{config.asset}'")
    registered = _HISTORICAL_PANEL_PATHS.get(config.historical_panel_key)
    if registered is None or registered[0] != config.asset:
        raise AssetConfigurationError(f"no historical panel is registered for '{config.asset}'")
    if settings is None:
        from valtide_api.config import get_settings

        settings = get_settings()
    return registered[1](settings)


__all__ = [
    "AssetConfig",
    "AssetCapabilities",
    "AssetConfigurationError",
    "AssetRegistryError",
    "UnsupportedAssetError",
    "is_supported_asset",
    "production_asset_configs",
    "resolve_asset_config",
    "resolve_historical_panel_path",
    "supported_asset_names",
]
