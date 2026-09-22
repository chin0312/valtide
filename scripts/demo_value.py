"""Demo: show how Valtide adds value, with an ex-post truth reveal.

Runs a scripted weekend where a lending protocol's collateral oracle is frozen
at Friday's close while the tokenized market sells off on news. Valtide flags the
oracle as CHALLENGED *before* the market reopens; then we reveal Monday's actual
open to score who was right.

This uses the real backend pipeline (quant_runtime + validation), only the market
data is stubbed. Run from the repo root:

    python scripts/demo_value.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.quant_runtime import load_artifact
from valtide_api.replay import run_inference
from valtide_api.state_store import KalmanState

# ── Stub scenario ────────────────────────────────────────────────────────────
FRI_CLOSE = 190.0  # NVDA close Friday
ORACLE = 190.0  # the protocol's collateral oracle — frozen at Friday close
MONDAY_OPEN = 184.2  # the truth, revealed only when the market reopens
FRI_TS = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
TOKEN_PATH = [
    ("2026-09-19T14:00:00Z", 189.2),
    ("2026-09-19T20:00:00Z", 188.0),
    ("2026-09-20T08:00:00Z", 186.3),
    ("2026-09-20T18:00:00Z", 185.1),
    ("2026-09-20T23:00:00Z", 184.4),
]


def _snap(ts: str, token: float) -> MarketSnapshot:
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=t,
        token_price=token,
        token_volume=80_000,
        underlying_reference=None,
        underlying_reference_ts=None,
        last_trusted_reference=FRI_CLOSE,
        last_trusted_reference_ts=FRI_TS,
        reference_age_seconds=int((t - FRI_TS).total_seconds()),
        reference_under_test=ORACLE,
        reference_under_test_source="protocol_oracle",
        market_state=MarketState.CLOSED,
    )


def main() -> None:
    art = load_artifact()
    state = KalmanState(m=art.m0, P=art.P0)

    print(f"WEEKEND — market closed, protocol oracle frozen at ${ORACLE:.0f}\n")
    print(f"  {'time':16} {'token':>7} {'oracle':>7} {'Valtide':>8} {'z':>6}  verdict")
    final = None
    for ts, token in TOKEN_PATH:
        result, state = run_inference(_snap(ts, token), state, artifact=art)
        print(
            f"  {ts[:16]:16} {token:>7.1f} {ORACLE:>7.1f} "
            f"{result.valtide_fair_value:>8.2f} {result.standardized_deviation:>6.2f}  "
            f"{result.evidence_state.value}"
        )
        final = result

    print(f"\nMONDAY OPEN (the truth, unknown all weekend): ${MONDAY_OPEN:.2f}\n")
    err_oracle = abs(ORACLE - MONDAY_OPEN)
    err_valtide = abs(final.valtide_fair_value - MONDAY_OPEN)
    err_token = abs(TOKEN_PATH[-1][1] - MONDAY_OPEN)
    print("  Closest to the real reopening price:")
    print(f"    protocol oracle : ${ORACLE:7.2f}  off ${err_oracle:5.2f} ({err_oracle/MONDAY_OPEN*100:.1f}%)")
    print(f"    raw token       : ${TOKEN_PATH[-1][1]:7.2f}  off ${err_token:5.2f} ({err_token/MONDAY_OPEN*100:.1f}%)")
    print(f"    VALTIDE         : ${final.valtide_fair_value:7.2f}  off ${err_valtide:5.2f} ({err_valtide/MONDAY_OPEN*100:.1f}%)")
    print(f"\n  Valtide's weekend verdict: {final.evidence_state.value}")
    print(f"  {(1 - err_valtide / err_oracle) * 100:.0f}% closer to the truth than the oracle.")
    print(f"  A protocol trusting the oracle over-valued collateral by "
          f"{(ORACLE / MONDAY_OPEN - 1) * 100:.1f}% — Valtide flagged it before reopening.")


if __name__ == "__main__":
    main()
