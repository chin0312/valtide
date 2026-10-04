#!/usr/bin/env bash
set -euo pipefail

ROOT="${VALTIDE_ROOT:-$HOME/valtide-p1ac}"
DATA_ROOT="${VALTIDE_DATA_ROOT:-$HOME/valtide-datasets}"
OUT_LOG="$ROOT/outputs/p1m_momentum_all.log"

mkdir -p "$ROOT/outputs"
: > "$OUT_LOG"

run_asset () {
  local ASSET="$1"
  local KEY="$2"
  local CACHE="$DATA_ROOT/$KEY"
  local P1A="$ROOT/outputs/$KEY/p1a_c"
  local CH="$ROOT/outputs/challenger_tail/$KEY/challenger_tail_report.json"
  local GATE="$ROOT/outputs/lag_dislocation_gate/$KEY/test_gate_scored_rows.csv"
  local OUT="$ROOT/outputs/$KEY/p1m_momentum"

  echo "===== STARTING $ASSET =====" | tee -a "$OUT_LOG"

  for f in \
    "$CACHE/canonical_panel_5m.csv" \
    "$CACHE/asset_metadata.json" \
    "$P1A/test_primary_intervals.csv" \
    "$P1A/P1a_full_fit.rds" \
    "$CH" \
    "$GATE"
  do
    if [[ ! -f "$f" ]]; then
      echo "ERROR: missing required file: $f" | tee -a "$OUT_LOG"
      exit 1
    fi
  done

  META_ASSET=$(python3 - "$CACHE/asset_metadata.json" <<'PY'
import json,sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    x=json.load(f)
print(x.get("asset_id",""))
PY
)
  if [[ "${META_ASSET,,}" != "${ASSET,,}" ]]; then
    echo "ERROR: requested $ASSET but metadata says $META_ASSET" | tee -a "$OUT_LOG"
    exit 1
  fi

  rm -rf "$OUT"
  mkdir -p "$OUT"

  (
    cd "$ROOT"
    VALTIDE_ASSET_ID="$ASSET" \
    VALTIDE_CACHE_DIR="$CACHE" \
    VALTIDE_OUTPUT_DIR="$OUT" \
    VALTIDE_P1A_DIR="$P1A" \
    VALTIDE_CHALLENGER_REPORT="$CH" \
    VALTIDE_GATE_SCORED="$GATE" \
    Rscript scripts/run_p1m_momentum_experiment.R
  ) > "$OUT/p1m.log" 2>&1

  echo "===== COMPLETE $ASSET =====" | tee -a "$OUT_LOG"
}

run_asset "NVDAx" "nvdax"
run_asset "SPYx"  "spyx"
run_asset "QQQx"  "qqqx"
run_asset "TSLAx" "tslax"
run_asset "AAPLx" "aaplx"

python3 - "$ROOT" <<'PY'
import csv, json, sys
from pathlib import Path

root = Path(sys.argv[1])
keys = ["nvdax","spyx","qqqx","tslax","aaplx"]
out = root / "outputs" / "p1m_momentum_summary"
out.mkdir(parents=True, exist_ok=True)

def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    fields=[]; seen=set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k); fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

params=[]
points=[]
targets=[]
chall=[]
intervals=[]
pseudo=[]

for k in keys:
    d=root/"outputs"/k/"p1m_momentum"
    params += read_csv(d/"P1m_parameters.csv")
    for r in read_csv(d/"test_point_estimate_comparison.csv"):
        if r.get("subset") == "ALL":
            r["asset_key"]=k
            points.append(r)
    for r in read_csv(d/"targeted_momentum_diagnostics.csv"):
        r["asset_key"]=k
        targets.append(r)
    for r in read_csv(d/"p1m_challenger_metrics.csv"):
        r["asset_key"]=k
        chall.append(r)
    for r in read_csv(d/"p1a_vs_p1m_interval_comparison.csv"):
        r["asset_key"]=k
        intervals.append(r)
    p=d/"pseudo_closure_metrics.csv"
    if p.exists():
        for r in read_csv(p):
            r["asset_key"]=k
            pseudo.append(r)

write_csv(out/"cross_asset_parameters.csv", params)
write_csv(out/"cross_asset_point_comparison.csv", points)
write_csv(out/"cross_asset_targeted_momentum.csv", targets)
write_csv(out/"cross_asset_challenger_metrics.csv", chall)
write_csv(out/"cross_asset_interval_comparison.csv", intervals)
write_csv(out/"cross_asset_pseudo_closure.csv", pseudo)

(out/"cross_asset_report.json").write_text(json.dumps({
    "note":"P1m is fitted independently per asset. No pooling.",
    "development_test_warning":"Current test periods have already been inspected in prior experiments; use results for development and confirm later on fresh untouched data.",
    "parameters":params,
    "point_comparison":points,
    "targeted_momentum":targets,
    "challenger_metrics":chall,
    "interval_comparison":intervals,
    "pseudo_closure":pseudo,
}, indent=2), encoding="utf-8")
PY

tar -czf "$HOME/valtide-p1m-momentum-results.tar.gz" \
  -C "$ROOT" \
  outputs/nvdax/p1m_momentum \
  outputs/spyx/p1m_momentum \
  outputs/qqqx/p1m_momentum \
  outputs/tslax/p1m_momentum \
  outputs/aaplx/p1m_momentum \
  outputs/p1m_momentum_summary \
  outputs/p1m_momentum_all.log

echo "ALL FIVE P1m EXPERIMENTS COMPLETE" | tee -a "$OUT_LOG"
echo "Archive: $HOME/valtide-p1m-momentum-results.tar.gz" | tee -a "$OUT_LOG"
