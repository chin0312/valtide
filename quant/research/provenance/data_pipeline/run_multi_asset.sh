#!/usr/bin/env bash
set -euo pipefail
START_UTC="${1:-2025-07-01T00:00:00Z}"
END_UTC="${2:-2026-09-20T23:59:59Z}"

assets=(
  "NVDAx NVDA"
  "SPYx SPY"
  "QQQx QQQ"
  "TSLAx TSLA"
  "AAPLx AAPL"
)

for pair in "${assets[@]}"; do
  read -r xstock underlying <<< "$pair"
  echo "=== $xstock / $underlying on Solana (chainIndex 501) ==="
  ./run_asset.sh "$xstock" "$underlying" "$START_UTC" "$END_UTC" Solana
done

echo "All five local Solana exports completed. Inspect exports/<asset>/ before GCP upload."
