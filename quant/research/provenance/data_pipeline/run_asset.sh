#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 XSTOCK_SYMBOL UNDERLYING_SYMBOL [START_UTC] [END_UTC] [NETWORK]" >&2
  exit 2
fi
export XSTOCK_SYMBOL="$1"
export UNDERLYING_SYMBOL="$2"
[[ $# -ge 3 ]] && export DATA_START_UTC="$3"
[[ $# -ge 4 ]] && export DATA_END_UTC="$4"
if [[ $# -ge 5 ]]; then
  export XSTOCK_NETWORK="$5"
else
  export XSTOCK_NETWORK="Solana"
fi
Rscript scripts/00_preflight.R
Rscript scripts/02_download_data.R
Rscript scripts/03_build_export.R
