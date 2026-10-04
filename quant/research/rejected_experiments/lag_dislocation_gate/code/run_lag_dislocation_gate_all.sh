#!/usr/bin/env bash
set -euo pipefail

ROOT="${VALTIDE_ROOT:-$HOME/valtide-p1ac}"
OUT="$ROOT/outputs/lag_dislocation_gate"
PY="$ROOT/scripts/train_lag_dislocation_gate.py"

mkdir -p "$OUT"
: > "$OUT/run.log"

run_asset () {
  local ASSET="$1"
  local KEY="$2"
  local P1="$ROOT/outputs/$KEY/p1a_c"
  local CH="$ROOT/outputs/challenger_tail/$KEY/challenger_tail_report.json"
  local AO="$OUT/$KEY"

  echo "===== START $ASSET =====" | tee -a "$OUT/run.log"

  if [[ ! -f "$P1/crossfit_scores.csv" || ! -f "$P1/test_primary_intervals.csv" ]]; then
    echo "ERROR: missing P1a-C outputs for $ASSET at $P1" | tee -a "$OUT/run.log"
    exit 1
  fi
  if [[ ! -f "$CH" ]]; then
    echo "ERROR: missing prior challenger report for $ASSET at $CH" | tee -a "$OUT/run.log"
    echo "Run challenger_tail_analysis first." | tee -a "$OUT/run.log"
    exit 1
  fi

  rm -rf "$AO"
  mkdir -p "$AO"

  python3 "$PY" \
    --asset "$ASSET" \
    --p1ac-dir "$P1" \
    --challenger-report "$CH" \
    --output-dir "$AO" \
    | tee "$AO/train.log"

  echo "===== COMPLETE $ASSET =====" | tee -a "$OUT/run.log"
}

run_asset "NVDAx" "nvdax"
run_asset "SPYx"  "spyx"
run_asset "QQQx"  "qqqx"
run_asset "TSLAx" "tslax"
run_asset "AAPLx" "aaplx"

python3 - "$OUT" <<'PY'
import csv, json, sys
from pathlib import Path

out = Path(sys.argv[1])
rows = []
for key in ["nvdax", "spyx", "qqqx", "tslax", "aaplx"]:
    p = out / key / "test_gate_metrics.csv"
    with p.open(newline="", encoding="utf-8") as f:
        rows.extend(csv.DictReader(f))

dest = out / "cross_asset_summary.csv"
fields = []
seen = set()
for r in rows:
    for k in r:
        if k not in seen:
            seen.add(k); fields.append(k)
with dest.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(rows)

summary = {
    "assets": len(rows),
    "note": "Each gate is trained independently on that asset's leakage-safe P1a cross-fit rows.",
    "rows": rows,
}
(out / "cross_asset_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(dest)
PY

tar -czf "$HOME/valtide-lag-dislocation-gate-results.tar.gz" \
  -C "$ROOT" outputs/lag_dislocation_gate

echo "ALL FIVE ASSETS COMPLETE"
echo "Archive: $HOME/valtide-lag-dislocation-gate-results.tar.gz"
