"""Scenario loader — turns an explicit scripted scenario into MarketSnapshots."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from valtide_api.models import MarketSnapshot
from valtide_api.session import classify

_SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_scenario(name: str = "weekend_divergence") -> list[MarketSnapshot]:
    """Load a scenario file and build one MarketSnapshot per step."""
    data = json.loads((_SCENARIO_DIR / f"{name}.json").read_text())
    asset = data["asset"]
    r0 = float(data["last_trusted_reference"])
    r0_ts = _parse_ts(data["last_trusted_reference_ts"])
    ref_source = data["reference_under_test_source"]

    snapshots: list[MarketSnapshot] = []
    for step in data["steps"]:
        obs_ts = _parse_ts(step["observation_ts"])
        nvda = step.get("underlying_reference")
        snapshots.append(
            MarketSnapshot(
                asset=asset,
                observation_ts=obs_ts,
                token_price=(
                    float(step["token_price"])
                    if step.get("token_price") is not None
                    else None
                ),
                token_volume=(
                    float(step["token_volume"])
                    if step.get("token_volume") is not None
                    else None
                ),
                underlying_reference=nvda,
                underlying_reference_ts=obs_ts if nvda is not None else None,
                last_trusted_reference=r0,
                last_trusted_reference_ts=r0_ts,
                reference_age_seconds=int((obs_ts - r0_ts).total_seconds()),
                reference_under_test=(
                    float(step["reference_under_test"])
                    if step.get("reference_under_test") is not None
                    else None
                ),
                reference_under_test_source=ref_source,
                reference_under_test_ts=(
                    obs_ts if step.get("reference_under_test") is not None else None
                ),
                reference_under_test_age_seconds=(
                    0 if step.get("reference_under_test") is not None else None
                ),
                market_state=classify(obs_ts),
                source_provenance={"scenario": name},
            )
        )
    return snapshots
