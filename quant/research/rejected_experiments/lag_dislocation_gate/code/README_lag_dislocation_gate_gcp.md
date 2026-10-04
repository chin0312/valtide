# Valtide — Lag vs Dislocation Gate (GCP)

> **Repository status:** This is a retained research procedure. Referenced GCP helper scripts and source datasets are not committed here, so remote commands described in this document are not executable from this checkout and their upload protections are not verified by CI.

## Purpose

This is the next experiment after the challenger-tail analysis.

The current challenger can detect large P1a–xStock disagreement, but NVDAx and TSLAx showed an important failure mode: sometimes **P1a is the one lagging a genuine move**. This package trains an **asset-specific gate** to distinguish:

- **P1a lag / genuine xStock move** → do not automatically escalate the disagreement, versus
- **xStock dislocation / P1a protective** → the challenger deserves a `REVIEW` flag.

It does **not** pool assets. NVDAx, SPYx, QQQx, TSLAx and AAPLx are trained independently.

## Leakage control

Training uses `crossfit_scores.csv`, where the P1a estimate is already out-of-fold. The underlying price is used only to create the historical label:

```text
p1a_better = 1 if |P1a - underlying| < |xStock - underlying|
```

The gate does **not** receive the current underlying price as a feature.

The gate is fitted only in the existing challenger `WATCH + REVIEW` zone (score >= cross-fit q80), because the question is specifically:

> when the independent model and xStock disagree, which side is more likely to be wrong?

The gate uses a chronological 70/30 internal fit/validation split to choose one of three fixed L2 penalties (`0.1, 1, 10`). The final selected penalty is refit on all cross-fit candidate rows, then evaluated on `test_primary_intervals.csv`.

Because we have already looked at the current test period during model development, treat these results as **development evidence**, not the final untouched claim. A later time period should be retained for final confirmation.

## Features

All are available at timestamp `t`:

- signed and absolute P1a–xStock disagreement,
- disagreement standardized by P1a predictive SD,
- P1a xStock innovation z-score,
- P1a predictive SD,
- xStock returns over 1 / 3 / 6 recent contiguous observations,
- P1a returns over 1 / 3 observations,
- change in challenger disagreement,
- recent xStock volatility,
- whether disagreement is aligned with recent xStock momentum,
- session state.

Rolling features reset after a gap >10 minutes so an overnight gap is not mistaken for a 5-minute return.

## Expected VM structure

```text
~/valtide-p1ac/
  scripts/
  outputs/
    nvdax/p1a_c/
    spyx/p1a_c/
    qqqx/p1a_c/
    tslax/p1a_c/
    aaplx/p1a_c/
    challenger_tail/
      nvdax/challenger_tail_report.json
      ...
```

## Upload

From Cloud Shell:

```bash
gcloud compute scp \
  ~/train_lag_dislocation_gate.py \
  ~/run_lag_dislocation_gate_all.sh \
  valtide-fit:~/valtide-p1ac/scripts/ \
  --zone=asia-southeast1-b
```

SSH:

```bash
gcloud compute ssh valtide-fit --zone=asia-southeast1-b
```

On the VM:

```bash
cd ~/valtide-p1ac
mv scripts/run_lag_dislocation_gate_all.sh ./run_lag_dislocation_gate_all.sh
chmod +x run_lag_dislocation_gate_all.sh
./run_lag_dislocation_gate_all.sh
```

No API keys, market-data calls, or third-party Python packages are required.

## Outputs

Per asset:

```text
outputs/lag_dislocation_gate/<asset>/
  gate_model.json
  gate_report.json
  validation_lambda_metrics.csv
  test_gate_metrics.csv
  status_error_profile.csv
  feature_coefficients.csv
  test_gate_scored_rows.csv
  train.log
```

Cross-asset:

```text
outputs/lag_dislocation_gate/
  cross_asset_summary.csv
  cross_asset_report.json
```

Archive:

```text
~/valtide-lag-dislocation-gate-results.tar.gz
```

## What to look for

The important comparison is **base REVIEW vs gated REVIEW**.

For NVDAx and TSLAx, we want the gate to raise:

```text
P1a-better rate in REVIEW
```

and ideally make:

```text
gated_review_p1a_mae_bps < gated_review_raw_mae_bps
```

without destroying recall of genuine xStock tail events.

For SPYx / QQQx / AAPLx, the gate should preserve the strong existing challenger behavior rather than filtering away most useful alerts.

The gate is successful if it makes `REVIEW` mean something more specific:

> xStock is behaving unusually **and** the independent P1a challenger is historically more likely to be informative than merely lagging the move.
