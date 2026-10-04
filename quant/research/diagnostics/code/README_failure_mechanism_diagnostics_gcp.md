# Valtide — Failure Mechanism Diagnostics (GCP)

> **Repository status:** This is a retained research procedure. Referenced GCP helper scripts and source datasets are not committed here, so remote commands described in this document are not executable from this checkout and their upload protections are not verified by CI.

This package implements the seven diagnostic tests we designed before training another challenger/gate.

## Why this stage exists

The lag-vs-dislocation gate improved NVDAx somewhat but did not solve TSLAx, and it reduced tail-event recall substantially. Before adding more model complexity, we need to determine **why P1a loses when it strongly disagrees with xStock**.

The working alternatives are:

1. **P1a lag / genuine information move**  
   xStock moved first and P1a was slow to follow.

2. **xStock dislocation**  
   xStock temporarily moved away from the underlying information state and P1a correctly resisted the move.

NVDAx and TSLAx are the primary cases. SPYx, QQQx and AAPLx are retained as controls.

## Tests implemented

### 1. Momentum/alignment
Within existing base `REVIEW` observations, bucket by absolute recent 15-minute xStock movement and whether the xStock movement is aligned with the P1a-xStock disagreement.

Useful signal for the lag hypothesis:
- P1a performs poorly when momentum is high and aligned with the disagreement.

Output:
`01_momentum_alignment.csv`

### 2. Volatility shock
Bucket `REVIEW` observations by recent xStock realized volatility.

Useful signal for the lag hypothesis:
- P1a win rate falls sharply in the highest-volatility bucket.

Output:
`02_volatility_buckets.csv`

### 3. Persistence vs reversion
For every base `REVIEW` row, inspect 5/15/30/60-minute future behavior.

The script decomposes convergence into:
- `p1a_catchup`: P1a moved toward the earlier xStock price;
- `xstock_reversion`: xStock moved back toward the earlier P1a price;
- `mixed_convergence`;
- `persistent_or_wider`.

It also measures whether the later underlying moves in the original xStock-disagreement direction.

**Future observations here are retrospective diagnostics only. They must never become live model inputs.**

Outputs:
- `03_forward_resolution_detail.csv`
- `03_forward_resolution_summary.csv`

### 4. Session/regime
Compare REVIEW behavior across regular, premarket, after-hours, overnight, etc.

Output:
`04_session_breakdown.csv`

### 5. Direction asymmetry
Separate:
- xStock above P1a;
- xStock below P1a.

This checks whether failures occur mainly on rallies or selloffs.

Output:
`05_direction_asymmetry.csv`

### 6. Episode-level analysis
Consecutive REVIEW observations separated by at most 10 minutes are merged into one economic episode.

Outputs include:
- episode duration;
- number of 5-minute alerts;
- maximum disagreement;
- maximum raw xStock error;
- P1a-better rate;
- whether any true tail event occurred;
- 30-minute resolution of the peak-disagreement observation.

Outputs:
- `06_review_episodes.csv`
- `06_episode_summary.csv`

### 7. Temporal stability
Repeat key behavior by month and by chronological blocks for both:
- cross-fit history;
- current test period.

This reveals whether a rule that worked earlier breaks later.

Outputs:
- `07_temporal_monthly.csv`
- `07_temporal_blocks.csv`

## Extra diagnostics

`feature_outcome_associations.csv`
compares feature values when P1a was actually better versus when P1a was worse inside REVIEW.

`largest_false_challenges.csv`
shows the largest cases where P1a strongly hurt rather than helped.

`largest_protective_challenges.csv`
shows the largest cases where P1a protected against raw xStock error.

These are intended to identify a stable mechanism before we decide what the next model should learn.

## Required existing VM outputs

```text
~/valtide-p1ac/
  outputs/
    nvdax/p1a_c/
    spyx/p1a_c/
    qqqx/p1a_c/
    tslax/p1a_c/
    aaplx/p1a_c/

    challenger_tail/
      nvdax/challenger_tail_report.json
      ...

    lag_dislocation_gate/
      nvdax/test_gate_scored_rows.csv
      ...
```

## Upload from Cloud Shell

```bash
gcloud compute scp \
  ~/diagnose_failure_mechanisms.py \
  ~/run_failure_mechanism_diagnostics_all.sh \
  valtide-fit:~/valtide-p1ac/scripts/ \
  --zone=asia-southeast1-b
```

## Run on VM

```bash
gcloud compute ssh valtide-fit --zone=asia-southeast1-b
```

Then:

```bash
cd ~/valtide-p1ac
mv scripts/run_failure_mechanism_diagnostics_all.sh ./run_failure_mechanism_diagnostics_all.sh
chmod +x run_failure_mechanism_diagnostics_all.sh

./run_failure_mechanism_diagnostics_all.sh
```

This does **not retrain P1a or the gate**, makes no API calls, and requires no third-party Python packages.

Expected final message:

```text
ALL DIAGNOSTICS COMPLETE
Archive: /home/james2001chen/valtide-failure-mechanism-diagnostics-results.tar.gz
```

## Retrieve results

Exit VM:

```bash
exit
```

From Cloud Shell:

```bash
gcloud compute scp \
  valtide-fit:~/valtide-failure-mechanism-diagnostics-results.tar.gz \
  ~/valtide-failure-mechanism-diagnostics-results.tar.gz \
  --zone=asia-southeast1-b
```

Upload that archive back to ChatGPT for interpretation.

## Decision rule after this stage

Do not train another complex model merely because a feature correlates with failures.

We should proceed only if the NVDAx/TSLAx diagnostics show a mechanism that is:
- economically interpretable;
- present in more than one chronological block;
- distinguishable from the SPYx/QQQx/AAPLx controls;
- based only on information observable at decision time.

A strong example would be:

> NVDAx/TSLAx false challenges consistently occur during high-momentum, high-volatility, aligned moves; P1a subsequently catches up while xStock remains close to the underlying.

That would justify training a resolver that explicitly recognizes a **P1a-lag state**.
