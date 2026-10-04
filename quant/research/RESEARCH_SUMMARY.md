# Valtide quantitative research summary

## Objective

The original objective was to test whether P1a/P1a-C could provide a better fair-value reference for xStocks, including intervals during periods when the underlying market is closed. The final evidence changes that interpretation: raw xStock is usually the better ordinary point estimate, while Valtide is most useful as an independent reference-reliability layer.

## What was tested

Five Solana xStocks—NVDAx, SPYx, QQQx, TSLAx and AAPLx—were evaluated over canonical five-minute panels from July 2025 through 20 September 2026. The work covered:

- P1a/P1a-C versus raw xStock/Raw-xStock-C;
- whether P1a–xStock disagreement detects tail errors;
- a learned lag-vs-dislocation gate;
- momentum, volatility, persistence/reversion, session, direction, episode and temporal diagnostics;
- the P1m momentum-augmented model and P1m-C intervals.

All later conclusions are development evidence: the test windows were repeatedly inspected during model development.

## What succeeded

Raw xStock remained the best ordinary center on average (five-asset mean MAE 5.17 bps vs 5.61 for P1a). P1a's advantage was concentrated in genuine xStock tails: across 681 true-tail observations, weighted MAE was about 15.9 bps for P1a versus 75.1 for raw, and P1a was closer about 97.1% of the time.

P1a–xStock disagreement strongly stratified reference risk for SPYx, QQQx and AAPLx. P1a-C also produced a lower 90% interval score than Raw-xStock-C on every asset, with clearly positive block-bootstrap differences on SPYx, QQQx, TSLAx and AAPLx and an inconclusive positive direction on NVDAx.

## What failed

P1a was not a universal price replacement. NVDAx and especially TSLAx often showed P1a lag during genuine high-momentum, high-volatility moves. The learned gate improved alert purity but discarded too many true tail events. P1m did not robustly reduce lag and sometimes collapsed toward raw xStock, destroying challenger independence; on TSLAx it worsened the targeted regimes.

## Interpretation and recommended architecture

The recommended architecture is:

1. raw xStock remains the primary observable point reference;
2. P1a supplies an independent challenger estimate;
3. P1a-C supplies calibrated uncertainty around that challenger;
4. the backend compares the observable reference and challenger and owns policy/status language;
5. REVIEW means that the reference deserves scrutiny, not that P1a must replace it.

Only the frozen NVDAx P1a-C package is included as runtime material. Cross-asset thresholds, the gate and P1m remain research/rejected branches and are not exposed through production import paths.

## What remains unvalidated

- Genuine closed-market fair value, because contemporaneous underlying truth does not exist during real closures.
- Stability in future market regimes and on a new chronological holdout.
- Production-grade challenger thresholds for each asset, especially NVDAx and TSLAx.
- Approved P1a/P1a-C runtime artifacts for SPYx, QQQx, TSLAx and AAPLx.
- A stable method to distinguish xStock dislocation from P1a lag without sacrificing tail recall.

Regenerate the compact metrics appendix from archived JSON outputs with:

```bash
python research/evaluation/regenerate_summary.py
```
