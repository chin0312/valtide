#!/usr/bin/env bash
# Build the real historical panel the demo uses, then verify it produces a
# CHALLENGED state. One command for the Dev Day demo.
#
# Prereqs: OKX and Alpaca keys set in .env (see .env.example):
#   OKX_API_KEY / OKX_API_SECRET / OKX_API_PASSPHRASE
#   ALPACA_API_KEY / ALPACA_API_SECRET
#
# Usage:
#   scripts/build_demo_panel.sh                 # default weekend window
#   scripts/build_demo_panel.sh START END       # custom UTC canonical range
#
# START/END are UTC, 5-minute aligned, e.g. 2026-09-18T14:00:00Z
set -euo pipefail
cd "$(dirname "$0")/.."

# A Fri-close -> Mon-open window, which is where NVDAx drifts from NVDA.
START="${1:-2026-09-18T14:00:00Z}"
END="${2:-2026-09-22T20:00:00Z}"
OUT="data/generated/nvdax_historical_5m.csv"   # the path source=auto looks for

PY="apps/api/.venv/bin/python"
[ -x "$PY" ] || PY="python"

echo "Building panel  $START -> $END"
PYTHONPATH=apps/api "$PY" scripts/build_historical_panel.py \
  --start "$START" --end "$END" --output "$OUT"

echo
echo "State distribution on the real panel:"
PYTHONPATH=apps/api "$PY" - <<'PYEOF'
from collections import Counter
from valtide_api.panel import load_panel_snapshots
from valtide_api.replay import replay
rows = replay(load_panel_snapshots("data/generated/nvdax_historical_5m.csv"))
c = Counter(r.evidence_state.value for r in rows)
for s in ("SUPPORTED", "INCONCLUSIVE", "CHALLENGED"):
    print(f"  {s:<13} {c.get(s,0)}")
ch = [r for r in rows if r.evidence_state.value == "CHALLENGED"]
if ch:
    f = ch[0]
    print(f"\nFirst CHALLENGED at {f.timestamp}  "
          f"token={f.token_price}  dev={f.reference_deviation_pct:.2f}%  "
          f"reasons={f.reason_codes}")
else:
    print("\nNO CHALLENGED in this window — pick a window with a real divergence.")
PYEOF

echo
echo "Done. The demo (source=auto) now uses this panel automatically."
echo "Verify via API:  curl 'localhost:8000/api/replay/NVDAx?source=panel' | head"
