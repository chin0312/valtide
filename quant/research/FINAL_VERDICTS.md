# Final candidate verdicts

These verdicts use the archived CSV/JSON outputs as the source of truth. `DEPLOYMENT_CANDIDATE` means approved for the stated narrow role, not universal superiority. The only fitted runtime bundle in this handoff is NVDAx P1a-C.

| Candidate | Verdict | Differentiation | Intended role | Decision basis |
|---|---|---|---|---|
| Raw xStock baseline | DEPLOYMENT_CANDIDATE | NEITHER | Primary observable point reference | Lower mean MAE than P1a across five assets: 5.17 vs 5.61 bps |
| P1a | DEPLOYMENT_CANDIDATE | REFERENCE_RELIABILITY | Independent challenger estimate; NVDAx frozen runtime only | Tail MAE 15.9 vs 75.1 bps for raw across 681 true-tail observations; not a universal replacement |
| P1a-C | DEPLOYMENT_CANDIDATE | REFERENCE_RELIABILITY | Calibrated uncertainty around the challenger; NVDAx frozen runtime only | Lower 90% interval score than Raw-xStock-C on all five assets; conservative 92.6–96.0% coverage |
| Raw-xStock-C | RESEARCH_ONLY | NEITHER | Calibration benchmark around raw xStock | Wider/weaker interval score than P1a-C; useful comparator, not selected runtime layer |
| Challenger tail detector | RESEARCH_ONLY | REFERENCE_RELIABILITY | Detect high-risk xStock states using P1a–xStock disagreement | Strong on SPYx/QQQx/AAPLx, weak precision/recall on NVDAx/TSLAx; thresholds need fresh validation |
| Lag-vs-dislocation gate | REJECTED | REFERENCE_RELIABILITY | Attempt to separate xStock dislocation from P1a lag | Improved REVIEW purity but tail recall fell to 12.0–52.9% across assets |
| P1m momentum model | REJECTED | PRICE_CORRECTION | Momentum-augmented replacement challenger | No robust improvement; TSLAx MAE worsened from 5.87 to 6.39 bps and QQQx collapsed toward raw |
| P1m-C | REJECTED | PRICE_CORRECTION | Calibrated uncertainty around P1m | Separately evaluated for SPYx, QQQx, TSLAx and AAPLx; inherited P1m failure and gave no general interval advantage |

## Raw xStock baseline

Raw xStock is the default ordinary point estimate. It beat P1a on MAE for NVDAx, QQQx and TSLAx, tied AAPLx, and lost clearly only for SPYx. It is not labelled `PRICE_CORRECTION` because it is the observed reference being assessed, not a differentiated Valtide model.

Limitations: rare large errors dominate its RMSE and are precisely where an independent challenger can be useful.

## P1a and P1a-C

P1a is approved only as an independent challenger. On true raw-xStock tail observations, P1a was closer 97.1% of the time in aggregate. P1a-C is approved as the corresponding uncertainty layer: 90% interval scores were 48.8/23.8/37.9/46.8/54.1 bps for NVDAx/SPYx/QQQx/TSLAx/AAPLx, versus 51.0/112.6/80.8/50.2/102.8 for Raw-xStock-C.

Limitations: the checked-in artifact is NVDAx-only; point and interval quality are separate; calibration is conservative; closed/overnight latent truth remains unobserved; the development test period is no longer untouched.

## Raw-xStock-C

Raw-xStock-C remains research evidence because it is the fair comparison showing that interval calibration alone does not rescue a point estimate in the same way across regimes. It was not selected for runtime because P1a-C had a lower interval score in every asset, although the NVDAx bootstrap difference was inconclusive (Raw-C minus P1a-C +2.20 bps, 95% CI -2.17 to 6.15).

## Challenger tail detector

The detector establishes the product thesis but is not promoted as frozen runtime logic. REVIEW-to-SUPPORT raw-error ratios were 37.3x for SPYx, 17.4x for QQQx and 11.4x for AAPLx, but only 4.4x for NVDAx and 3.1x for TSLAx. A REVIEW flag therefore means scrutiny, never automatic substitution.

## Lag-vs-dislocation gate

The gate improved P1a-better rates in REVIEW—for example NVDAx 31.2% to 55.2% and QQQx 73.8% to 91.7%—but reduced true-tail recall too severely: NVDAx 61.4% to 18.0%, SPYx 100% to 45.3%, QQQx 98.6% to 52.9%, TSLAx 49.5% to 12.1%, AAPLx 92.8% to 12.0%. It is rejected as a replacement detector.

## P1m and P1m-C

P1m did not fix the targeted failure state. On TSLAx high-momentum REVIEW rows, MAE worsened from P1a 27.08 to P1m 30.73 bps; on prior false challenges it worsened from 20.98 to 24.54 bps while raw was 5.34 bps. QQQx P1m became nearly identical to raw and lost P1a's true-tail protection. NVDAx was not rerun. P1m and P1m-C are rejected rather than merely deferred because the stated hypothesis failed on the inspected evidence.
