# Valtide — P1m Momentum Challenger Experiment

> **Repository status:** This is a retained research procedure. Referenced GCP helper scripts and source datasets are not committed here, so remote commands described in this document are not executable from this checkout and their upload protections are not verified by CI.

## What this tests

The failure-mechanism diagnostics suggested a specific P1a weakness:

> On NVDAx and especially TSLAx, fast persistent xStock moves are often genuine price discovery. P1a smooths too aggressively, lags the move, and falsely challenges xStock.

This package implements **P1m**, a parsimonious momentum-augmented state-space challenger.

It is still fitted **separately for every asset**. There is no pooling.

## Model

P1a uses a random-walk latent value. P1m adds a persistent local trend plus one causal quant momentum factor:

```text
m_t = m_(t-1) + v_(t-1) + beta * M_(t-1) + eta_m,t
v_t = rho * v_(t-1) + eta_v,t

underlying_t = m_t + eps_u,t
xStock_t     = m_t + eps_x,t
```

Where:

- `m_t` = latent current underlying value in log-price space;
- `v_t` = latent short-horizon velocity/trend;
- `M_(t-1)` = EWMA of prior xStock 5-minute log returns;
- `rho` = trend persistence;
- `beta` = how strongly the causal momentum factor shifts the prior;
- `eta_m`, `eta_v` = process innovations.

The EWMA uses `alpha = 0.35`.

**Important:** the momentum feature at timestamp `t` contains returns only through `t-1`. The current xStock print is then assimilated as an observation. This avoids using the same current print both as a momentum predictor and a measurement.

Relative to P1a, the model adds only three global parameters:

```text
q_velocity
rho
beta_momentum
```

The existing P1a session-specific level process noise and observation-noise structure are retained.

## Why this is deliberately small

We already inspected NVDA/TSLA failure cases. Adding many momentum indicators now would make it easy to fit those historical errors.

P1m therefore tests one narrow hypothesis:

> Does allowing persistent short-term drift reduce P1a's high-momentum lag without destroying its ability to resist genuine xStock dislocations?

If this works, richer momentum factors can be considered later. If it does not, adding RSI/MACD/etc. would not be well justified.

## Training / leakage protection

For each asset independently:

1. Keep the same original chronological train/test split.
2. Inside training data, fit P1m on the same expanding cross-fit folds used for P1a-C.
3. Select the interval calibration family from cross-fit data only.
4. Fit P1m on the complete original training sample.
5. Replay the development test causally:
   - predict with trend + lagged momentum;
   - observe current xStock;
   - record P1m estimate;
   - compare against the hidden current underlying;
   - only then assimilate the underlying for the next timestamp.

P1a fit files are used only as optimizer warm-starts for common variance parameters.

### Important evaluation limitation

The current test periods have already been inspected in earlier Valtide experiments. Therefore this is now **development evidence**, not a pristine final holdout.

Any final selected model must later be confirmed on genuinely newer untouched data.

## Tests produced

### A. Normal point accuracy

`test_point_estimate_comparison.csv`

Compares on identical test rows:

```text
raw xStock
P1a
P1m
```

with MAE, RMSE and win rates.

### B. Targeted momentum failure test

`targeted_momentum_diagnostics.csv`

This is the key file.

P1m is evaluated on the exact historical regions where the previous P1a challenger struggled:

```text
ALL
BASE_REVIEW
TRUE_TAIL
REVIEW_HIGH_MOMENTUM_Q4
REVIEW_HIGH_VOL_Q4
REVIEW_P1A_FALSE
```

For NVDAx/TSLAx, the strongest success criterion is:

```text
P1m MAE < P1a MAE
```

inside `REVIEW_HIGH_MOMENTUM_Q4` and `REVIEW_P1A_FALSE`.

But it should not achieve this merely by collapsing onto raw xStock everywhere.

### C. Challenger ability

P1m gets its own disagreement score:

```text
|xStock - P1m|
```

Its WATCH/REVIEW thresholds are frozen from P1m cross-fit history.

Outputs:

```text
p1m_challenger_metrics.csv
p1m_challenger_status_profile.csv
```

This tells us whether the momentum fix preserves the original Valtide goal:

> identify occasions when xStock is unusually unreliable.

### D. Interval estimate

P1m receives the same empirical P1a-C calibration procedure, producing P1m-C.

Output:

```text
p1a_vs_p1m_interval_comparison.csv
```

### E. Pseudo-closure

The underlying is hidden continuously for:

```text
30 / 60 / 120 / 240 minutes
```

Output:

```text
pseudo_closure_metrics.csv
```

This checks whether adding momentum reduces the severe drift/lag observed in longer pseudo-closures.

## Required VM state

The existing VM should already contain:

```text
~/valtide-p1ac/
~/valtide-datasets/nvdax/
~/valtide-datasets/spyx/
~/valtide-datasets/qqqx/
~/valtide-datasets/tslax/
~/valtide-datasets/aaplx/
```

and prior outputs:

```text
outputs/<asset>/p1a_c/
outputs/challenger_tail/<asset>/
outputs/lag_dislocation_gate/<asset>/
```

No secrets or APIs are used.

## Upload from Cloud Shell

Upload these three files to Cloud Shell, then:

```bash
gcloud compute scp \
  ~/momentum_state_model.R \
  ~/run_p1m_momentum_experiment.R \
  ~/run_p1m_momentum_all.sh \
  valtide-fit:~/ \
  --zone=asia-southeast1-b
```

SSH into the VM:

```bash
gcloud compute ssh valtide-fit --zone=asia-southeast1-b
```

Install them:

```bash
cd ~/valtide-p1ac

mv ~/momentum_state_model.R R/momentum_state_model.R
mv ~/run_p1m_momentum_experiment.R scripts/run_p1m_momentum_experiment.R
mv ~/run_p1m_momentum_all.sh ./run_p1m_momentum_all.sh

chmod +x run_p1m_momentum_all.sh
```

## Run

Because this fits 4 cross-fit models + 1 full model for each of five assets, use `tmux`:

```bash
tmux new-session -d -s p1m_momentum \
'cd ~/valtide-p1ac && ./run_p1m_momentum_all.sh'
```

Monitor overall progress:

```bash
tail -f ~/valtide-p1ac/outputs/p1m_momentum_all.log
```

Monitor the currently running asset, e.g. NVDAx:

```bash
tail -f ~/valtide-p1ac/outputs/nvdax/p1m_momentum/p1m.log
```

Check process:

```bash
ps -eo pid,etime,%cpu,%mem,cmd | grep '[r]un_p1m_momentum_experiment.R'
```

Completion message:

```text
ALL FIVE P1m EXPERIMENTS COMPLETE
Archive: /home/james2001chen/valtide-p1m-momentum-results.tar.gz
```

## Retrieve

Exit the VM:

```bash
exit
```

From Cloud Shell:

```bash
gcloud compute scp \
  valtide-fit:~/valtide-p1m-momentum-results.tar.gz \
  ~/valtide-p1m-momentum-results.tar.gz \
  --zone=asia-southeast1-b
```

Download that archive and upload it back to ChatGPT.

## What would count as success?

The desired result is **not simply lower overall MAE**.

P1m succeeds if it shows this combination:

1. NVDAx/TSLAx:
   - materially lower error than P1a in high-momentum false-challenge states;
   - fewer cases where P1a/P1m wrongly resists a genuine move.

2. SPYx/QQQx/AAPLx:
   - retains most of P1a's protection in true xStock dislocations.

3. Challenger detection:
   - `REVIEW` still has much higher raw-xStock error than `SUPPORT`;
   - tail-event precision/recall do not collapse.

4. Pseudo-closure:
   - less deterioration as the hidden-reference period increases.

That would support the interpretation that momentum was a real missing state variable rather than an asset-specific patch.
