#!/usr/bin/env bash
set -euo pipefail

cd "$HOME/valtide-p1ac"

mkdir -p outputs/challenger_tail

python3 scripts/challenger_tail_analysis.py \
  --outputs-root outputs \
  --assets nvdax,spyx,qqqx,tslax,aaplx \
  --out outputs/challenger_tail \
  --relative-tail-q 0.95 \
  --fixed-tail-bps 25,50 \
  | tee outputs/challenger_tail/run.log

tar -czf "$HOME/valtide-challenger-tail-results.tar.gz" \
  -C "$HOME/valtide-p1ac" outputs/challenger_tail

echo
echo "Created: $HOME/valtide-challenger-tail-results.tar.gz"
ls -lh "$HOME/valtide-challenger-tail-results.tar.gz"
