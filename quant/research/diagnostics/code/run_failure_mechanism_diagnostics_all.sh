#!/usr/bin/env bash
set -euo pipefail

ROOT="${VALTIDE_ROOT:-$HOME/valtide-p1ac}"
OUT="$ROOT/outputs/failure_mechanism_diagnostics"
PY="$ROOT/scripts/diagnose_failure_mechanisms.py"

mkdir -p "$OUT"
: > "$OUT/run.log"

run_asset () {
  local ASSET="$1"
  local KEY="$2"
  local P1="$ROOT/outputs/$KEY/p1a_c"
  local CH="$ROOT/outputs/challenger_tail/$KEY/challenger_tail_report.json"
  local GATE="$ROOT/outputs/lag_dislocation_gate/$KEY"
  local AO="$OUT/$KEY"

  echo "===== START $ASSET =====" | tee -a "$OUT/run.log"

  for f in \
    "$P1/test_primary_intervals.csv" \
    "$P1/crossfit_scores.csv" \
    "$CH" \
    "$GATE/test_gate_scored_rows.csv"
  do
    if [[ ! -f "$f" ]]; then
      echo "ERROR: required file missing: $f" | tee -a "$OUT/run.log"
      exit 1
    fi
  done

  rm -rf "$AO"
  mkdir -p "$AO"

  python3 "$PY" \
    --asset "$ASSET" \
    --p1ac-dir "$P1" \
    --challenger-report "$CH" \
    --gate-dir "$GATE" \
    --output-dir "$AO" \
    | tee "$AO/diagnostic.log"

  echo "===== COMPLETE $ASSET =====" | tee -a "$OUT/run.log"
}

# NVDAx and TSLAx are the primary failure cases.
# The other three are deliberately retained as controls.
run_asset "NVDAx" "nvdax"
run_asset "TSLAx" "tslax"
run_asset "SPYx"  "spyx"
run_asset "QQQx"  "qqqx"
run_asset "AAPLx" "aaplx"

python3 - "$OUT" <<'PY'
import csv, json, sys
from pathlib import Path

out = Path(sys.argv[1])
keys = ["nvdax","tslax","spyx","qqqx","aaplx"]

def read_one(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write(path, rows):
    fields=[]; seen=set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k); fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

summary=[]
forward=[]
episodes=[]
for k in keys:
    summary += read_one(out/k/"diagnostic_summary.csv")
    forward += read_one(out/k/"03_forward_resolution_summary.csv")
    episodes += read_one(out/k/"06_episode_summary.csv")

write(out/"cross_asset_diagnostic_summary.csv", summary)
write(out/"cross_asset_forward_resolution.csv", forward)
write(out/"cross_asset_episode_summary.csv", episodes)

(out/"cross_asset_report.json").write_text(json.dumps({
    "primary_failure_assets":["nvdax","tslax"],
    "control_assets":["spyx","qqqx","aaplx"],
    "note":"Diagnostics only; no model was trained in this stage.",
    "summary":summary,
    "forward_resolution":forward,
    "episode_summary":episodes,
}, indent=2), encoding="utf-8")
PY

tar -czf "$HOME/valtide-failure-mechanism-diagnostics-results.tar.gz" \
  -C "$ROOT" outputs/failure_mechanism_diagnostics

echo "ALL DIAGNOSTICS COMPLETE"
echo "Archive: $HOME/valtide-failure-mechanism-diagnostics-results.tar.gz"
