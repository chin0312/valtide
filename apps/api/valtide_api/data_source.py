"""Resolve explicit scenario and historical-panel replay sources.

Live valuation never calls this module. Keeping replay source selection here
prevents a missing historical panel from silently becoming a live result.
"""

from __future__ import annotations

from pathlib import Path

from valtide_api.config import get_settings
from valtide_api.models import MarketSnapshot
from valtide_api.panel import load_panel_snapshots
from valtide_api.scenario import load_scenario

# valtide_api/ -> apps/api/ -> apps/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PANEL = _REPO_ROOT / "data" / "sample" / "p0_panel_5m.csv"


def resolve_snapshots(
    source: str = "auto",
    scenario: str = "weekend_divergence",
    panel_path: str | Path | None = None,
) -> tuple[list[MarketSnapshot], str]:
    """Return (snapshots, source_label).

    ``source=auto`` uses a generated/sample panel when one exists and otherwise
    explicitly falls back to the scripted scenario. It never feeds either mode
    into the warmed-live cache.
    """
    generated_panel = get_settings().resolved_historical_panel_path
    selected_panel = Path(panel_path) if panel_path is not None else None
    if selected_panel is None:
        selected_panel = generated_panel if generated_panel.exists() else _DEFAULT_PANEL

    if source in {"panel", "historical", "historical_panel"}:
        return load_panel_snapshots(selected_panel), "historical_panel"
    if source == "scenario":
        return load_scenario(scenario), "scenario"
    if source == "auto":
        if selected_panel.exists():
            return load_panel_snapshots(selected_panel), "historical_panel"
        return load_scenario(scenario), "scenario"
    raise ValueError(f"unsupported replay source: {source}")
