# Module 1 — Local Solana xStocks data collection

This module downloads xStock market data from **Solana (OKX chainIndex `501`)** and the corresponding U.S. underlying from Alpaca **on your local machine**, builds a timestamp-aligned 5-minute panel, audits price scale, and emits a sanitized dataset for the GCP P1a-C module.

The multi-asset experiment uses these five pairs:

| xStock | Underlying |
|---|---|
| NVDAx | NVDA |
| SPYx | SPY |
| QQQx | QQQ |
| TSLAx | TSLA |
| AAPLx | AAPL |

## Security boundary

Market-data credentials remain local. Put real credentials only in a local `.Renviron` file. `.Renviron` is gitignored and is **never part of the GCP export**.

Do **not** copy `data/raw/` to GCP. Module 2 uploads only the sanitized files under `exports/<asset>/`.

Raw OKX response captures, if enabled, also remain under `data/raw/` locally. Authentication headers, API keys, signatures and passphrases are never written into those capture files.

## 1. Install R dependencies

From this directory:

```powershell
Rscript 00_install_packages.R
```

## 2. Create the local secret file

Copy `.Renviron.example` to `.Renviron` and fill in your OKX OnchainOS and Alpaca credentials.

Keep asset/date/network options out of `.Renviron`; the wrappers set those as process variables. Never commit or upload the real `.Renviron`.

## 3. Recommended: download all five Solana assets

PowerShell:

```powershell
.\run_multi_asset.ps1 `
  -StartUtc "2025-07-01T00:00:00Z" `
  -EndUtc "2026-09-20T23:59:59Z"
```

Bash:

```bash
./run_multi_asset.sh 2025-07-01T00:00:00Z 2026-09-20T23:59:59Z
```

For every asset the downloader:

1. discovers all matching xStock deployments,
2. **filters to Solana / chainIndex `501` first**,
3. selects the highest-`volume24h` Solana deployment if more than one exists,
4. saves that exact chain/address to `data/raw/<asset>/selected_deployment.csv`,
5. reuses the pinned deployment on subsequent runs,
6. downloads the underlying from Alpaca,
7. builds the canonical local panel and sanitized export.

This prevents an asset from silently switching to Ethereum or another chain between runs.

## 4. Download one asset

Solana is now the default network.

PowerShell:

```powershell
.\run_asset.ps1 -XStock TSLAx -Underlying TSLA `
  -StartUtc "2025-07-01T00:00:00Z" `
  -EndUtc "2026-09-20T23:59:59Z"
```

Equivalent explicit form:

```powershell
.\run_asset.ps1 -XStock TSLAx -Underlying TSLA `
  -StartUtc "2025-07-01T00:00:00Z" `
  -EndUtc "2026-09-20T23:59:59Z" `
  -Network "Solana"
```

Bash:

```bash
./run_asset.sh TSLAx TSLA 2025-07-01T00:00:00Z 2026-09-20T23:59:59Z Solana
```

## 5. Inspect deployment discovery

To see every candidate and verify the Solana candidate before downloading:

```powershell
$env:XSTOCK_SYMBOL="TSLAx"
$env:UNDERLYING_SYMBOL="TSLA"
$env:XSTOCK_NETWORK="Solana"
Rscript scripts/01_discover_asset.R
```

The script writes:

```text
data/raw/tslax/okx_deployments.csv
```

and identifies the highest-volume matching deployment on chain `501`.

### Optional exact deployment override

If you need to reproduce a run with an exact already-known Solana mint, set both values:

```powershell
$env:OKX_CHAIN_INDEX="501"
$env:OKX_TOKEN_ADDRESS="<exact Solana token address>"
```

The downloader refuses an override whose chain index conflicts with `XSTOCK_NETWORK`.

Unset these variables to return to automatic Solana discovery.

## 6. Output

For `TSLAx`, the upload-safe folder is:

```text
exports/tslax/
├── canonical_panel_5m.csv
├── asset_metadata.json
├── dataset.sha256
├── data_audit.csv
└── scale_check.csv
```

`asset_metadata.json` records the selected OKX deployment, including the chain index and token address.

Only this `exports/<asset>/` folder is intended for Module 2 / GCP.

The panel contains asset-neutral columns such as `underlying_close` and `token_close`, plus legacy `nvda_*` / `nvdax_*` aliases required by the current P1a implementation. For non-NVDA assets, those aliases simply mean "underlying" and "xStock"; they do not change the asset identity.

## 7. Scale / corporate-action guard

Before declaring the export usable, the build script checks the median overlapping `token_close / underlying_close` ratio. If it differs from 1 by more than `SCALE_RATIO_TOLERANCE` (2% by default), the script stops.

Inspect the locally downloaded xStocks multiplier history and normalize corporate actions before proceeding; do not bypass the check merely to force a model run.

## 8. Cache reuse and refresh

Each asset gets a separate local raw cache. Later runs extend only missing date ranges.

The cache identity includes the chain index and token address. If you switch from an old Ethereum cache to Solana, the token cache is not treated as the same dataset.

To force a complete refresh:

```powershell
$env:FORCE_REFRESH_DATA="true"
.\run_asset.ps1 -XStock TSLAx -Underlying TSLA
$env:FORCE_REFRESH_DATA="false"
```

## 9. Handoff to Module 2 / GCP

For each asset, give Module 2 the sanitized export only:

```text
DATASET_PATH=<this-module>/exports/tslax/canonical_panel_5m.csv
METADATA_PATH=<this-module>/exports/tslax/asset_metadata.json
ASSET_ID=TSLAx
```

Repeat for `nvdax`, `spyx`, `qqqx`, `tslax`, and `aaplx`.

Module 2 deliberately stages only model code plus these sanitized files. It does **not** upload this module, `.Renviron`, raw market data, raw HTTP responses, or market-data credentials.

## 10. Optional raw OKX response capture

The downloader can save the exact JSON response-body bytes received from OKX **before parsing**.

Enable:

```powershell
$env:OKX_CAPTURE_RAW_RESPONSES="true"
```

Captures stay local under:

```text
data/raw/<asset>/okx_http_raw/
├── <request>.json
└── <request>.meta.json
```

The metadata contains only safe request information and hashes. No API key, secret, signature, passphrase, or authorization header is written.

If a requested interval is already cached but you want a fresh raw response for that exact window:

```powershell
$env:OKX_REQUERY_REQUESTED_WINDOW="true"
```

For normal full-history downloads, leave both raw-capture flags unset/false.
