"""Resolve explicit scenario and historical-panel replay sources.

Live valuation never calls this module. Keeping replay source selection here
prevents a missing historical panel from silently becoming a live result.
"""

from __future__ import annotations

from pathlib import Path

from valtide_api.assets import (
    AssetConfigurationError,
    resolve_asset_config,
    resolve_historical_panel_path,
)
from valtide_api.config import get_settings
from valtide_api.models import MarketSnapshot
from valtide_api.panel import load_panel_snapshots
from valtide_api.scenario import load_scenario


def resolve_snapshots(
    source: str = "auto",
    scenario: str = "weekend_divergence",
    panel_path: str | Path | None = None,
    *,
    asset: str = "NVDAx",
) -> tuple[list[MarketSnapshot], str]:
    """Return (snapshots, source_label).

    ``source=auto`` uses the configured/generated panel when one exists and
    otherwise explicitly falls back to the scripted scenario. It never feeds
    either mode into the warmed-live cache.
    """
    settings = get_settings()
    asset_config = resolve_asset_config(asset, settings)
    selected_panel = Path(panel_path) if panel_path is not None else None

    if source == "scenario":
        return _validate_asset_snapshots(load_scenario(scenario), asset), "scenario"

    if source in {"panel", "historical", "historical_panel"}:
        if selected_panel is None:
            selected_panel = resolve_historical_panel_path(asset_config, settings)
        snapshots = load_panel_snapshots(selected_panel, asset=asset, settings=settings)
        return _validate_asset_snapshots(snapshots, asset), _panel_source_label(snapshots)
    if source == "auto":
        if selected_panel is None:
            try:
                selected_panel = resolve_historical_panel_path(asset_config, settings)
            except AssetConfigurationError:
                # Retain the original NVDA demo fallback only. Other assets may
                # never inherit its synthetic fixture as historical evidence.
                if asset == "NVDAx":
                    return _validate_asset_snapshots(load_scenario(scenario), asset), "scenario"
                raise
        if selected_panel is not None and selected_panel.exists():
            snapshots = load_panel_snapshots(selected_panel, asset=asset, settings=settings)
            return _validate_asset_snapshots(snapshots, asset), _panel_source_label(snapshots)
        if asset == "NVDAx":
            return _validate_asset_snapshots(load_scenario(scenario), asset), "scenario"
        raise AssetConfigurationError(f"historical panel is unavailable for asset '{asset}'")
    raise ValueError(f"unsupported replay source: {source}")


def _panel_source_label(snapshots: list[MarketSnapshot]) -> str:
    if snapshots and snapshots[0].source_provenance.get("panel_schema") == "legacy_nvda_diagnostic":
        return "legacy_nvda_panel_diagnostic"
    return "historical_panel"


def _validate_asset_snapshots(
    snapshots: list[MarketSnapshot],
    asset: str,
) -> list[MarketSnapshot]:
    """Reject a source fixture that is bound to a different asset."""

    if any(snapshot.asset != asset for snapshot in snapshots):
        raise AssetConfigurationError(
            f"data source returned observations for an asset other than '{asset}'"
        )
    return snapshots
