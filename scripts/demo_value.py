"""Run the backend's canonical scripted replay as a narrated demo.

The scenario data are illustrative. The optional reopening comparison is a
synthetic ex-post benchmark, not an observed market truth.

Run from the repository root:

    python scripts/demo_value.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from valtide_api.replay import replay
from valtide_api.scenario import load_scenario

SYNTHETIC_EX_POST_BENCHMARK = 184.2


def main() -> None:
    snapshots = load_scenario("weekend_divergence")
    results = replay(snapshots)

    print("WEEKEND DIVERGENCE — illustrative scenario replay\n")
    print(f"  {'time':16} {'token':>8} {'reference':>10} {'Valtide':>9} {'z':>7}  evidence")
    for snapshot, result in zip(snapshots, results, strict=True):
        token = f"{snapshot.token_price:.1f}" if snapshot.token_price is not None else "—"
        reference = (
            f"{snapshot.reference_under_test:.1f}"
            if snapshot.reference_under_test is not None
            else "—"
        )
        z = (
            f"{result.standardized_deviation:.2f}"
            if result.standardized_deviation is not None
            else "—"
        )
        print(
            f"  {result.timestamp.isoformat()[:16]:16} {token:>8} {reference:>10} "
            f"{result.valtide_fair_value:>9.2f} {z:>7}  {result.evidence_state.value}"
        )

    final = results[-1]
    print(
        f"\nSYNTHETIC EX-POST BENCHMARK (illustrative, not observed truth): "
        f"${SYNTHETIC_EX_POST_BENCHMARK:.2f}"
    )
    print(
        f"  final challenger estimate: ${final.valtide_fair_value:.2f}"
        f"  | evidence: {final.evidence_state.value}"
    )


if __name__ == "__main__":
    main()
