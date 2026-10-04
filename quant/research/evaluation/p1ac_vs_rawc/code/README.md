# Module 2 — Sanitized GCP P1a-C evaluation

> **Checkout limitation:** This is a preserved workflow description, not a runnable GCP module in the current repository. The referenced `gcp/*.sh` helper scripts, prepared source panel, and `.Renviron.example` are not included. Commands below that invoke `gcp/` therefore cannot run from this checkout. The uploader's whitelist and secret-scan behavior cannot be independently verified until the exact scripts are restored and reviewed. No raw data or credentials should be added to make CI pass.

This module uploads **only a prepared dataset plus the P1a/P1a-C model code** to Google Compute Engine, runs the expanding-window P1a-C calibration/evaluation, and downloads the result bundle.

It deliberately contains **no market-data downloader**. OKX/Alpaca/xStocks collection and all market-data credentials stay in Module 1 on your local machine.

## Security design

The original external procedure states that `gcp/upload_project.sh` creates a temporary whitelist stage containing only:

```text
R/ + config/ + scripts/ + selected gcp helpers
00_install_packages.R
README.md
canonical_panel_5m.csv
asset_metadata.json
dataset.sha256
```

It is intended to exclude `.Renviron`, `.env`, raw data, prior outputs, local package libraries, and gcloud credential files. Because the helper is absent, those protections are documentation claims, not verified behavior of a script in this checkout.

Your `gcloud auth` credentials remain in your local Google Cloud CLI configuration; they are not copied into the archive.

## 1. Prerequisites on your local machine

Install/authenticate Google Cloud CLI:

```bash
gcloud auth login
```

Set non-secret GCP parameters:

```bash
export PROJECT_ID="YOUR_GCP_PROJECT_ID"
export VM_NAME="valtide-fit"
export ZONE="asia-southeast1-b"
```

Enable Compute Engine once if needed:

```bash
gcloud services enable compute.googleapis.com
```

## 2. Create the VM

From this module:

```bash
bash gcp/create_vm.sh
```

The default is `c4-standard-8`, 50 GB, Ubuntu 24.04, no GPU.

## 3. Point at Module 1's sanitized export

Example for TSLAx:

```bash
export ASSET_ID="TSLAx"
export DATASET_PATH="../01_local_data/exports/tslax/canonical_panel_5m.csv"
export METADATA_PATH="../01_local_data/exports/tslax/asset_metadata.json"
```

Do **not** point `DATASET_PATH` at Module 1's `data/raw/` directory.

## 4. Upload the sanitized bundle

```bash
bash gcp/upload_project.sh
```

The uploader verifies the dataset SHA against `asset_metadata.json`. Any mismatch stops the upload.

## 5. Run P1a-C

```bash
bash gcp/start_p1a_c_remote.sh
```

By default:

```text
VALTIDE_REUSE_FITS=false
```

This is intentional for cross-asset testing. A previous NVDAx fit must not be reused on TSLAx, SPYx, etc. If you explicitly enable reuse later, the R script still checks that the saved fit has the same `asset_id` and dataset SHA256.

Check progress:

```bash
bash gcp/status_p1a_c_remote.sh
```

## 6. Download results

```bash
bash gcp/download_p1a_c_remote.sh
```

For TSLAx the archive will be named:

```text
valtide-tslax-p1ac-results.tar.gz
```

After extracting it, the main performance files are:

```text
test_interval_metrics.csv
candidate_validation_metrics.csv
test_block_bootstrap_vs_gaussian.csv
pseudo_closure_metrics.csv
closed_market_replay.csv
p1a_c_report.json
p1a_c_calibrator.json
```

The 90% `ALL` rows of `test_interval_metrics.csv` contain coverage, interval width, interval score, MAE and RMSE. `test_block_bootstrap_vs_gaussian.csv` compares calibrated P1a-C against the original Gaussian interval using trading-date blocks. `pseudo_closure_metrics.csv` tests 30/60/120/240-minute periods where the underlying is deliberately hidden.

If you run the model locally after downloading/extracting the output directory, set `VALTIDE_OUTPUT_DIR` and use:

```bash
Rscript scripts/summarize_p1ac.R
```

## 7. Repeat for another xStock

Run Module 1 again for the next asset, then rerun this module with a new `ASSET_ID`, `DATASET_PATH`, and `METADATA_PATH`. `upload_project.sh` replaces the remote code/data bundle, so there is no opportunity for an old asset's input dataset to remain silently active.

## Cost control

When finished:

```bash
gcloud compute instances stop "$VM_NAME" --zone="$ZONE"
```

Delete the VM when no longer needed:

```bash
gcloud compute instances delete "$VM_NAME" --zone="$ZONE"
```

## P1a-C vs Raw-xStock-C comparison

For the stronger baseline experiment, use `scripts/run_p1ac_vs_rawc.R`. It preserves P1a-C and adds a calibration-only baseline whose center estimate is the raw xStock price.

The comparison uses the same chronological 80/20 split and the same expanding cross-fit fold boundaries for both calibration layers. The untouched test set is not used for calibration selection.

Run from the module root:

```bash
VALTIDE_ASSET_ID=NVDAx \
VALTIDE_CACHE_DIR=data/cache \
VALTIDE_OUTPUT_DIR=outputs/nvdax/p1a_c \
VALTIDE_REUSE_VALID_PRIOR=true \
P1AC_BOOTSTRAP_REPS=2000 \
Rscript scripts/run_p1ac_vs_rawc.R
```

`VALTIDE_REUSE_VALID_PRIOR=true` may reuse earlier P1a cross-fit scores and a full P1a fit only when the saved manifest/fitted object matches both the current asset id and exact dataset SHA256. Set it to `false` to force all P1a fits to be recomputed.

New outputs include:

- `test_point_estimate_comparison.csv`
- `test_interval_metrics_comparison.csv`
- `raw_candidate_validation_metrics.csv`
- `raw_xstock_c_calibrator.json`
- `test_block_bootstrap_rawc_vs_p1ac.csv`
- `raw_pseudo_closure_metrics.csv`
- `pseudo_closure_comparison.csv`
- `p1ac_vs_rawc_report.json`

Summarize with:

```bash
VALTIDE_OUTPUT_DIR=outputs/nvdax/p1a_c Rscript scripts/summarize_p1ac_vs_rawc.R
```
