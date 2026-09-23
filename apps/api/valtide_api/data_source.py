"""Chooses the snapshot source: James's real panel if present, else the scenario.

Keeps the "where do snapshots come from" decision in one place so the replay
route and the startup seed stay consistent. When James's p0_panel_5m.csv is
dropped into data/sample/, the app automatically switches from the scripted
scenario to real data — no code change needed.
"""

from __future__ import annotations

from pathlib import Path

from valtide_api.models import MarketSnapshot
from valtide_api.panel import load_panel_snapshots
from valtide_api.scenario import load_scenario

# valtide_api/ -> apps/api/ -> apps/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PANEL = _REPO_ROOT / "data" / "sample" / "p0_panel_5m.csv"


def resolve_snapshots(
    source: str = "auto", scenario: str = "weekend_divergence"
) -> tuple[list[MarketSnapshot], str]:
    """Return (snapshots, source_label).

    source="auto"     -> panel if the CSV exists, else scenario
    source="panel"    -> panel (raises if missing)
    source="scenario" -> the named scenario
    """
    if source == "panel" or (source == "auto" and _DEFAULT_PANEL.exists()):
        return load_panel_snapshots(_DEFAULT_PANEL), "panel"
    return load_scenario(scenario), "scenario"
