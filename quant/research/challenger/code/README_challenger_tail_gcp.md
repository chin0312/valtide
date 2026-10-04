# Valtide challenger-tail analysis — GCP

> **Repository status:** This is a retained research procedure. The referenced GCP helper scripts and source datasets are not committed here, so remote commands described in this document are not executable from this checkout and their upload protections are not verified by CI.

This analysis directly tests the challenger-model hypothesis:

> When Valtide/P1a materially disagrees with the raw xStock, does that disagreement identify observations where the raw xStock is unusually far from the hidden contemporaneous underlying price?

It **does not retrain P1a** and **does not call any market-data API**. It only reads the completed P1a-C vs Raw-C outputs already on the VM.

## Leakage-safe design

For each asset, the script uses:

- `crossfit_scores.csv`: out-of-fold observations from the training period.
- `test_primary_intervals.csv`: untouched chronological test observations.

The script first computes three challenger scores using only information available before the hidden underlying is revealed:

1. `disagreement_bps = |xStock - P1a|` in log-price basis points.
2. `disagreement_z = |xStock - P1a| / P1a predictive SD`.
3. `innovation_abs_z = |xStock innovation z-score|`.

On **cross-fit training data only**, it defines an asset-relative raw-xStock tail event as the worst 5% of raw xStock tracking errors. It chooses the challenger score with the highest average precision for that tail event, with AUROC as a tie-breaker.

Still using cross-fit training data only, the chosen score's 80th and 95th percentiles are frozen as challenger thresholds:

- below q80: `SUPPORT`
- q80 to q95: `WATCH`
- q95 and above: `REVIEW`

Only after these rules are frozen does the script evaluate them on the untouched test set using the hidden contemporaneous underlying price.

The hidden underlying benchmark is used **only for evaluation**, not to construct the challenger score or status.

## What it tests

The output answers four questions:

1. Does a larger ex-ante challenger score predict a larger raw xStock error?
2. Does `REVIEW` concentrate actual raw-xStock tail errors?
3. When a true tail error occurs, does P1a reduce that error relative to raw xStock?
4. Is the direction of the P1a challenge usually toward the subsequently revealed underlying price?

Both an asset-relative tail event (OOF-training 95th percentile) and fixed 25/50 bp error events are evaluated.

## Upload to the existing VM

From Cloud Shell, after uploading the two files to your Cloud Shell home directory:

```bash
gcloud compute scp \
  ~/challenger_tail_analysis.py \
  ~/run_challenger_tail_all.sh \
  valtide-fit:~/valtide-p1ac/scripts/ \
  --zone=asia-southeast1-b
```

SSH to the VM:

```bash
gcloud compute ssh valtide-fit --zone=asia-southeast1-b
```

Then place the wrapper at project root (or invoke it from `scripts/`):

```bash
cd ~/valtide-p1ac
mv scripts/run_challenger_tail_all.sh ./run_challenger_tail_all.sh
chmod +x run_challenger_tail_all.sh
```

## Run

```bash
cd ~/valtide-p1ac
./run_challenger_tail_all.sh
```

This should be much faster than fitting P1a because it only analyzes existing CSV outputs.

## Outputs

The script creates:

```text
outputs/challenger_tail/
├── cross_asset_summary.csv
├── cross_asset_report.json
├── run.log
├── nvdax/
│   ├── challenger_tail_report.json
│   ├── candidate_score_metrics.csv
│   ├── detection_metrics.csv
│   ├── status_error_profile.csv
│   ├── tail_reduction_metrics.csv
│   ├── top_score_metrics.csv
│   └── test_challenger_scored_rows.csv
├── spyx/
├── qqqx/
├── tslax/
└── aaplx/
```

The wrapper also creates:

```text
~/valtide-challenger-tail-results.tar.gz
```

## Most important files

### `cross_asset_summary.csv`
One-line summary per asset. Important fields:

- `selected_score`
- `test_score_raw_error_spearman`
- `test_relative_tail_auroc`
- `test_relative_tail_average_precision`
- `review_raw_mae_bps`
- `support_raw_mae_bps`
- `review_to_support_raw_error_ratio`
- `review_mean_tail_reduction_bps`
- `review_p1a_better_rate`

A useful challenger should ideally show:

```text
REVIEW raw error >> SUPPORT raw error
```

and, if P1a is proposed as a corrective challenger:

```text
REVIEW mean tail reduction > 0
P1a-better rate in REVIEW > 50%
```

### `status_error_profile.csv`
Shows actual hidden-reference errors inside `SUPPORT`, `WATCH`, and `REVIEW`. This directly tests whether the operational challenge statuses stratify xStock reliability.

### `detection_metrics.csv`
For relative-q95, 25 bp, and 50 bp raw-xStock error events, reports precision, recall, false-positive rate, AUROC, and average precision.

### `tail_reduction_metrics.csv`
Conditions on actual xStock tail errors and asks whether P1a reduced them and whether `REVIEW`/`WATCH` caught them.

## Download results

After the run finishes, exit back to Cloud Shell and copy the archive:

```bash
gcloud compute scp \
  valtide-fit:~/valtide-challenger-tail-results.tar.gz \
  ~/valtide-challenger-tail-results.tar.gz \
  --zone=asia-southeast1-b
```

Then download `/home/james2001chen/valtide-challenger-tail-results.tar.gz` from the Cloud Shell file-download dialog.

## Interpretation limitation

This test validates ex-ante detection against **historically observed contemporaneous underlying prices that were hidden from the model**. It does not prove that the same error rates or calibration hold during a genuine weekend when no contemporaneous underlying price exists. That remains a separate closed-market validation problem.
