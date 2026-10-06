"""Canonical asset identities and capability declarations.

Being listed in the API catalog is not proof that an asset has a fitted model,
historical panel, scheduler, or X Layer binding. Those are independent,
fail-closed readiness layers.
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
    """Immutable application/data identity for one registered asset."""

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
    reference_profile: str
    # The Registry reference identity is intentionally distinct from the vendor
    # instrument name.  It is the existing public identity hashed in the
    # deployment manifest and must not be changed by this refactor.
    xlayer_reference_name: str
    quant_runtime_key: str
    historical_panel_key: str
    capabilities: AssetCapabilities


_NVDA_CONFIG = AssetConfig(
    asset="NVDAx",
    underlying_symbol="NVDA",
    token_source="okx_onchainos",
    underlying_source="alpaca",
    token_market_key="okx_onchainos",
    okx_chain_index="501",
    token_address="Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh",
    allow_token_discovery=False,
    reference_under_test_source="okx_xperp_index",
    reference_under_test_instrument="NVDA-USD",
    # This single product pipeline consumes Solana xStock as the model input,
    # its corresponding underlying, and the separate OKX X-Perp index evidence.
    # The prior profile remains only on already-persisted legacy rows.
    reference_profile="unified_xstock_p1ac_xperp_evidence_v1",
    xlayer_reference_name="OKX_NVDA_USD_INDEX",
    quant_runtime_key="nvdax_p1ac_default",
    historical_panel_key="nvdax_panel",
    capabilities=AssetCapabilities(True, True, True, True, True, True),
)

_PRIMARY_TOKEN_DEPLOYMENTS = {
    "SPYx": ("SPY", "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W", "SPY-USD"),
    "QQQx": ("QQQ", "Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ", "QQQ-USD"),
    "AAPLx": ("AAPL", "XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp", "AAPL-USD"),
}


def _xstock_asset_config(
    asset: str, underlying: str, token_address: str, index_instrument: str
) -> AssetConfig:
    key = asset.lower()
    # QQQx stays available to offline quant/historical research but is not
    # exposed, live-enabled, or runtime-enabled through production HTTP.
    research_only = asset == "QQQx"
    return AssetConfig(
        asset=asset,
        underlying_symbol=underlying,
        token_source="okx_onchainos",
        underlying_source="alpaca",
        token_market_key="okx_onchainos",
        okx_chain_index="501",
        token_address=token_address,
        allow_token_discovery=False,
        reference_under_test_source="okx_xperp_index",
        reference_under_test_instrument=index_instrument,
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1",
        xlayer_reference_name=f"OKX_{underlying}_USD_INDEX",
        quant_runtime_key=f"{key}_p1ac_v030",
        historical_panel_key=f"{key}_panel",
        capabilities=AssetCapabilities(
            live_data=not research_only,
            historical_data=True,
            quant=True,
            runtime=not research_only,
            onchain=not research_only,
            api_exposed=not research_only,
        ),
    )


_PRIMARY_CONFIGS = tuple(
    _xstock_asset_config(asset, underlying, token_address, index_instrument)
    for asset, (underlying, token_address, index_instrument) in _PRIMARY_TOKEN_DEPLOYMENTS.items()
)

_TSLA_CANDIDATE = AssetConfig(
    asset="TSLAx",
    underlying_symbol="TSLA",
    token_source="okx_onchainos",
    underlying_source="alpaca",
    token_market_key="okx_onchainos",
    okx_chain_index="501",
    token_address="XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB",
    allow_token_discovery=False,
    reference_under_test_source="xstock_token_market",
    reference_under_test_instrument="TSLAx",
    reference_profile="xstock_vs_p1ac_challenger",
    xlayer_reference_name="XSTOCK_TSLA_USD_REFERENCE",
    quant_runtime_key="tslax_p1ac_unfitted",
    historical_panel_key="tslax_panel",
    capabilities=AssetCapabilities(
        live_data=True,
        historical_data=True,
        api_exposed=False,
    ),
)

# Keep this mapping private and immutable.  A future asset must be added only
# with an explicit review of its behavioral, quant, and deployment bindings.
_ASSET_REGISTRY: Mapping[str, AssetConfig] = MappingProxyType(
    {
        config.asset: config
        for config in (_NVDA_CONFIG, *_PRIMARY_CONFIGS, _TSLA_CANDIDATE)
    }
)

_HISTORICAL_PANEL_PATHS: Mapping[str, tuple[str, Callable[[Settings], Path | None]]] = (
    MappingProxyType({
        "nvdax_panel": ("NVDAx", lambda settings: settings.resolved_historical_panel_path),
        "spyx_panel": ("SPYx", lambda settings: settings.resolved_spyx_historical_panel_path),
        "qqqx_panel": ("QQQx", lambda settings: settings.resolved_qqqx_historical_panel_path),
        "aaplx_panel": ("AAPLx", lambda settings: settings.resolved_aaplx_historical_panel_path),
        "tslax_panel": ("TSLAx", lambda settings: settings.resolved_tslax_historical_panel_path),
    })
)


def supported_asset_names() -> tuple[str, ...]:
    """Return registered production asset names in deterministic order."""

    return tuple(
        config.asset
        for config in _ASSET_REGISTRY.values()
        if config.capabilities.api_exposed
    )


def api_asset_configs() -> tuple[AssetConfig, ...]:
    """Return immutable API-catalog configs, including explicitly unready assets."""

    return tuple(
        config
        for config in _ASSET_REGISTRY.values()
        if config.capabilities.api_exposed
    )


def resolve_asset_config(asset: str, settings: Settings | None = None) -> AssetConfig:
    """Resolve one registered asset, including its backward-compatible values.

    Unknown assets fail before any source, quant artifact, SQLite state, or
    deployment metadata is selected. The NVDAx environment names remain the
    compatibility boundary for its existing source configuration.
    """

    config = _ASSET_REGISTRY.get(asset)
    if config is None:
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
        if chain_index and (
            chain_index != config.okx_chain_index or token_address != config.token_address
        ):
            raise AssetConfigurationError(
                "NVDAx deployment override does not match the registered Solana token identity"
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
            reference_under_test_instrument=reference_instrument,
        )

    if bool(config.okx_chain_index) != bool(config.token_address):
        raise AssetConfigurationError("token chain index and address must be configured together")
    if not config.allow_token_discovery and not config.okx_chain_index:
        raise AssetConfigurationError(f"token deployment must be pinned for '{asset}'")
    return config


def is_supported_asset(asset: str) -> bool:
    """Return whether ``asset`` is included in the public asset catalog."""

    return asset in supported_asset_names()


def resolve_historical_panel_path(config: AssetConfig, settings: Settings | None = None) -> Path:
    """Resolve an explicitly registered asset panel; never inherit NVDA's path."""
    if not config.capabilities.historical_data:
        raise AssetConfigurationError(f"historical data is unavailable for '{config.asset}'")
    registered = _HISTORICAL_PANEL_PATHS.get(config.historical_panel_key)
    if registered is None or registered[0] != config.asset:
        raise AssetConfigurationError(f"no historical panel is registered for '{config.asset}'")
    if settings is None:
        from valtide_api.config import get_settings

        settings = get_settings()
    path = registered[1](settings)
    if path is None:
        raise AssetConfigurationError(f"historical panel is not configured for '{config.asset}'")
    return path


def historical_panel_available(config: AssetConfig, settings: Settings | None = None) -> bool:
    """Return whether a canonical panel is identity-verified for this asset."""
    try:
        return inspect_historical_panel(config, settings).canonical_identity_verified
    except AssetConfigurationError:
        return False


def historical_panel_file_available(
    config: AssetConfig, settings: Settings | None = None
) -> bool:
    """Return file presence only; this is deliberately not a readiness claim."""
    try:
        return resolve_historical_panel_path(config, settings).is_file()
    except (AssetConfigurationError, OSError):
        return False


def inspect_historical_panel(config: AssetConfig, settings: Settings | None = None):
    """Inspect registered panel identity/readiness without running replay."""
    from valtide_api.panel import PanelReadiness, inspect_panel_readiness

    try:
        path = resolve_historical_panel_path(config, settings)
    except AssetConfigurationError:
        return PanelReadiness(False, error_code="PANEL_NOT_CONFIGURED")
    return inspect_panel_readiness(path, asset=config.asset, settings=settings)


def registered_asset_configs() -> tuple[AssetConfig, ...]:
    """Return every registered identity, including non-public research candidates."""
    return tuple(_ASSET_REGISTRY.values())


__all__ = [
    "AssetConfig",
    "AssetCapabilities",
    "AssetConfigurationError",
    "AssetRegistryError",
    "UnsupportedAssetError",
    "is_supported_asset",
    "historical_panel_available",
    "historical_panel_file_available",
    "inspect_historical_panel",
    "api_asset_configs",
    "registered_asset_configs",
    "resolve_asset_config",
    "resolve_historical_panel_path",
    "supported_asset_names",
]
