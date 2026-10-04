# Valtide P1a-C — Feature Freeze Evidence Summary

**Evidence window:** 3–4 Oct 2026  
**Purpose:** Record the new empirical evidence gathered around P1a-C before feature freeze, including what is now supported, what failed, and what remains unproven.

## Executive conclusion

The last two days materially changed how P1a-C should be interpreted. **P1a-C should not be treated as a replacement point-price oracle for xStock.** Raw xStock is usually the better average point estimate. The strongest evidence for P1a-C is instead that **P1a often protects against extreme xStock errors, and P1a–xStock disagreement can act as a useful challenger signal in some assets.** That ability is strong for SPYx, QQQx and AAPLx, but materially weaker for NVDAx and TSLAx because P1a can lag genuine fast-moving price discovery. Attempts to fix this through a learned gate and through direct momentum augmentation did not produce a sufficiently robust improvement, so neither should enter the frozen model.

---

## 1. Raw xStock remains the stronger default point estimate

On the untouched development test blocks, raw xStock had lower MAE than P1a for NVDAx, QQQx and TSLAx, was essentially tied for AAPLx, and lost clearly only for SPYx.

| Asset | Raw xStock MAE | P1a MAE | Raw RMSE | P1a RMSE | Point-estimate result |
|---|---:|---:|---:|---:|---|
| NVDAx | **5.16 bps** | 6.76 bps | **9.04** | 10.42 | Raw better |
| SPYx | 5.45 bps | **3.02 bps** | 17.83 | **4.62** | P1a better |
| QQQx | **4.03 bps** | 5.45 bps | 9.93 | **9.26** | Raw better on MAE; P1a trims some tail error |
| TSLAx | **4.25 bps** | 5.87 bps | **7.35** | 9.00 | Raw better |
| AAPLx | **6.95 bps** | 6.96 bps | 14.65 | **11.98** | MAE effectively tied; P1a lowers RMSE |

Across the five assets, simple mean MAE was **5.17 bps for raw xStock vs 5.61 bps for P1a**. However, mean RMSE was **11.76 bps for raw vs 9.05 bps for P1a**, which was the first indication that P1a may be more valuable in extreme-error states than in ordinary observations.

**Feature-freeze interpretation:** raw xStock should remain the default observable center; P1a-C is better framed as an independent challenger/risk layer.

---

## 2. P1a has strong protection specifically when xStock is genuinely in the tail

The strongest new evidence is the tail-error experiment. A “true tail” was defined per asset using the **95th percentile of raw-xStock error learned from cross-fit training data**, then evaluated on the untouched test block.

| Asset | Tail threshold | Tail observations | Raw MAE in true tail | P1a MAE in true tail | P1a closer rate |
|---|---:|---:|---:|---:|---:|
| NVDAx | 27.83 bps | 189 | 45.01 | **25.19** | **96.3%** |
| SPYx | 57.73 bps | 170 | 126.16 | **7.30** | **100%** |
| QQQx | 48.33 bps | 140 | 65.26 | **4.57** | **100%** |
| TSLAx | 31.03 bps | 99 | 45.00 | **33.33** | **86.9%** |
| AAPLx | 59.36 bps | 83 | 91.20 | **11.02** | **100%** |

Across all **681 true-tail observations**, weighted raw-xStock MAE was approximately **75.1 bps**, versus **15.9 bps for P1a**; P1a was closer on approximately **97.1%** of those observations.

This is the clearest evidence supporting P1a as a challenger: **its comparative advantage is concentrated in rare, large xStock errors rather than in average pricing.**

---

## 3. P1a–xStock disagreement can identify unreliable xStock states, but not uniformly across assets

We then tested whether an ex-ante challenger score—computed without the current underlying price—could identify those bad xStock observations. The selected score was generally P1a–xStock disagreement (standardized disagreement for NVDAx).

| Asset | Raw MAE in SUPPORT | Raw MAE in REVIEW | REVIEW / SUPPORT error ratio | REVIEW precision for true tail | REVIEW recall |
|---|---:|---:|---:|---:|---:|
| NVDAx | 4.28 | 18.91 | **4.4×** | 24.8% | 41.8% |
| SPYx | 3.38 | 125.74 | **37.3×** | **98.8%** | **99.4%** |
| QQQx | 2.94 | 51.27 | **17.4×** | **67.0%** | **90.0%** |
| TSLAx | 3.65 | 11.37 | **3.1×** | 8.7% | 37.4% |
| AAPLx | 5.41 | 61.82 | **11.4×** | **54.2%** | **85.5%** |

The signal is therefore very strong for SPYx, strong for QQQx/AAPLx, but weak for NVDAx/TSLAx. Even in NVDAx/TSLAx, REVIEW observations have materially higher raw-xStock error than SUPPORT, so disagreement still contains risk information; the problem is that **large disagreement does not reliably tell us which side is wrong.**

**Feature-freeze interpretation:** challenger disagreement is supported as a risk signal, but REVIEW must not automatically replace xStock with P1a.

---

## 4. P1a-C provides materially sharper calibrated intervals than the tested Raw-xStock-C baseline

At the nominal 90% interval level, P1a-C had a lower interval score than Raw-xStock-C for all five assets. Lower interval score is better because it penalizes both excessive width and misses.

| Asset | P1a-C coverage | P1a-C width | P1a-C interval score | Raw-C coverage | Raw-C width | Raw-C interval score |
|---|---:|---:|---:|---:|---:|---:|
| NVDAx | 94.3% | 37.1 bps | **48.8** | 97.3% | 43.0 | 51.0 |
| SPYx | 96.0% | 20.4 bps | **23.8** | 93.0% | 67.5 | 112.6 |
| QQQx | 93.2% | 28.4 bps | **37.9** | 97.2% | 67.7 | 80.8 |
| TSLAx | 95.7% | 38.2 bps | **46.8** | 98.3% | 46.1 | 50.2 |
| AAPLx | 92.6% | 35.8 bps | **54.1** | 96.4% | 90.7 | 102.8 |

Block-bootstrap differences in interval score (Raw-C minus P1a-C) were clearly positive for SPYx (**+88.6 bps, 95% CI 68.7 to 111.9**), QQQx (**+42.7, CI 37.1 to 48.4**), TSLAx (**+3.43, CI 0.95 to 5.36**) and AAPLx (**+48.2, CI 40.2 to 55.5**). NVDAx was inconclusive (**+2.20, CI -2.17 to 6.15**).

P1a-C still over-covered relative to 90%, generally around **92.6–96.0%**, so calibration is conservative. Raw-C was often even more conservative, especially where historical xStock residuals were much noisier than the later test period.

**Feature-freeze interpretation:** P1a-C's calibrated uncertainty remains one of the strongest retained components, but interval quality should not be confused with point-estimate superiority.

---

## 5. The main NVDAx/TSLAx failure mechanism is P1a lag during genuine fast moves

Failure-mechanism diagnostics showed that P1a's weak challenger performance in NVDAx and TSLAx is strongly associated with high momentum and high volatility.

For **NVDAx REVIEW** observations, moving from the lowest to highest aligned 15-minute momentum quartile changed P1a performance from:

- P1a win rate: **44.4% → 11.2%**
- P1a MAE: **14.93 → 38.21 bps**
- Raw xStock MAE: **13.69 → 14.04 bps**

For **TSLAx REVIEW** observations:

- P1a win rate: **31.0% → 9.4%**
- P1a MAE: **13.70 → 27.08 bps**
- Raw xStock MAE: **8.82 → 9.47 bps**

The volatility split showed the same direction. In the highest-volatility quartile, P1a win rate fell to **23.3% for NVDAx** and **13.3% for TSLAx**.

The forward-resolution diagnostic also supports a lag interpretation. Thirty minutes after an existing REVIEW:

- **TSLAx:** P1a moved **16.46 bps toward the earlier xStock price**, while xStock reverted only **0.96 bps**.
- **NVDAx:** P1a moved **18.59 bps toward xStock**, while xStock reverted **7.66 bps**.

By contrast, the control assets often showed the opposite behavior:

- **SPYx:** at 30 minutes, xStock reversion dominated in **92.1%** of REVIEW cases; at 60 minutes, **95.1%**.
- **QQQx:** xStock reversion dominated in **69.5%** at 30 minutes and **70.3%** at 60 minutes.
- **AAPLx:** xStock reversion dominated in **65.4%** at 30 minutes and **66.2%** at 60 minutes.

This is strong evidence that P1a disagreement has **two distinct economic meanings**: sometimes xStock is dislocated and P1a is protective; sometimes xStock is discovering a genuine move faster and P1a is lagging.

---

## 6. A learned “lag vs dislocation” gate improved alert quality but sacrificed too much recall

A regularized asset-specific gate was trained to estimate whether P1a was more likely to be right when P1a and xStock disagreed.

It improved the quality of REVIEW for several assets:

- **NVDAx:** P1a-better rate in REVIEW rose from **31.2% to 55.2%**; P1a MAE improved from being worse than raw (**23.89 vs 15.27 bps**) to slightly better (**16.50 vs 18.90 bps**).
- **QQQx:** P1a-better rate rose from **73.8% to 91.7%**; gated REVIEW P1a MAE was **7.92 bps vs raw 56.85 bps**.
- **AAPLx:** P1a-better rate rose from **68.0% to 84.6%**; gated REVIEW P1a MAE was **13.99 bps vs raw 45.73 bps**.
- **TSLAx:** P1a-better rate improved from **21.2% to 45.7%**, but P1a still lost on MAE (**14.87 vs raw 13.60 bps**).

However, tail recall collapsed:

- NVDAx: **61.4% → 18.0%**
- SPYx: **100% → 45.3%**
- QQQx: **98.6% → 52.9%**
- TSLAx: **49.5% → 12.1%**
- AAPLx: **92.8% → 12.0%**

**Feature-freeze interpretation:** the gate is useful research evidence, but should not replace the simpler challenger detector in the frozen model because it filters out too many genuine tail events.

---

## 7. Direct momentum augmentation did not improve P1a robustly and should not enter the freeze

We tested a momentum-augmented state-space model, P1m, with a latent trend state plus causal EWMA xStock momentum. This was intended to reduce NVDA/TSLA lag.

The result did not support adopting P1m:

| Asset | Raw MAE | P1a MAE | P1m MAE | Result |
|---|---:|---:|---:|---|
| SPYx | 5.45 | **3.02** | 3.03 | Essentially unchanged |
| QQQx | **4.03** | 5.45 | **4.03** | P1m effectively collapsed toward raw xStock |
| TSLAx | **4.25** | 5.87 | 6.39 | **Worse than P1a** |
| AAPLx | **6.95** | 6.96 | 6.97 | Essentially unchanged |

TSLAx is especially important because its learned momentum coefficient was meaningful (**beta ≈ 0.230**), yet performance worsened exactly where the hypothesis predicted improvement:

- high-momentum REVIEW: **P1a 27.08 bps → P1m 30.73 bps**
- high-volatility REVIEW: **P1a 25.64 bps → P1m 29.77 bps**
- prior false-challenge states: **P1a 20.98 bps → P1m 24.54 bps**, while raw xStock was only **5.34 bps**

QQQx exposed an even more important risk: P1m reduced its xStock observation variance almost to zero and became nearly identical to raw xStock. Overall MAE improved to raw's **4.03 bps**, but on true-tail observations P1a remained **4.57 bps** while P1m/raw were approximately **65.26 bps**. In other words, making the challenger follow xStock more aggressively can destroy the very independence that makes P1a useful in dislocations.

**Feature-freeze interpretation:** momentum is evidence about **regime/trust**, not a justified additive fair-value factor. P1m is rejected for the frozen model.

---

## 8. P1a challenger behavior is materially non-stationary over time

The new temporal diagnostics show that P1a's effectiveness in REVIEW states changes substantially across chronological periods.

Examples:

- **NVDAx cross-fit REVIEW P1a-better rate:** **75.1% → 64.6% → 46.8% → 33.0%** across four successive training blocks. In the test blocks it ranged from **10.8% to 58.7%**.
- **TSLAx cross-fit REVIEW:** **61.4% → 45.1% → 38.1% → 23.9%**; test blocks remained weak at roughly **16–26%**.
- **QQQx test REVIEW:** **28.2% and 13.8%** in the first two blocks, then **90.0% and 93.7%** in the final two blocks.
- **AAPLx test REVIEW:** **6.7% and 39.5%** in the first two blocks, then **88.9% and 85.7%** in the final two blocks.

This non-stationarity is a major reason not to overfit another static gate to the currently inspected test period.

**Feature-freeze interpretation:** freeze the current research architecture rather than continue feature tuning on the same data. Any future model change should be evaluated on a genuinely newer chronological holdout.

---

## Feature-freeze decision

### Retain

- **P1a** as an independent challenger estimate, not the default market price.
- **P1a-C calibration** as the uncertainty layer around the challenger.
- **Raw xStock as the primary observable point reference** under ordinary conditions.
- **P1a–xStock disagreement / standardized disagreement** as a challenger-risk signal.
- `SUPPORT / WATCH / REVIEW` framing, with the explicit caveat that REVIEW means **“the existing valuation deserves scrutiny”**, not **“P1a is definitely the correct replacement price.”**

### Do not add before freeze

- The lag-vs-dislocation classifier as a hard gate: it improved REVIEW purity but destroyed tail recall.
- Direct momentum/trend augmentation (P1m): it did not robustly improve P1a and in QQQx risked collapsing the challenger onto raw xStock.
- Asset-specific hand-tuned rules designed to repair NVDAx/TSLAx on the already inspected period.

### Claims supported by current evidence

1. **Raw xStock is generally an excellent ordinary point reference.**
2. **P1a is disproportionately useful when raw xStock is genuinely far from the contemporaneous underlying.**
3. **P1a–xStock disagreement can identify high-risk valuation states very effectively for SPYx, QQQx and AAPLx, and more weakly for NVDAx/TSLAx.**
4. **P1a-C produces substantially sharper uncertainty intervals than the tested Raw-xStock-C baseline on four assets and directionally better intervals on NVDAx.**
5. **Fast momentum is a documented failure mode for P1a in NVDAx/TSLAx, but directly injecting momentum into fair value is not supported by the P1m experiment.**

### Claims not yet supported

- That P1a-C estimates the unobservable “true” fair value during genuine weekends/market closures.
- That a REVIEW flag is universally equivalent to xStock mispricing.
- That P1a should automatically replace xStock after a REVIEW flag.
- That the current performance will remain stable in future regimes.

The next evidence milestone after feature freeze should therefore be **fresh, untouched chronological validation**, especially across genuine closure periods and new xStock market regimes, rather than further tuning on the current development sample.

---

## Source result artifacts used

- `valtide-five-asset-p1ac-vs-rawc-results.tar.gz`
- `valtide-challenger-tail-results.tar.gz`
- `valtide-lag-dislocation-gate-results.tar.gz`
- `valtide-failure-mechanism-diagnostics-results.tar.gz`
- `valtide-p1m-momentum-results.tar.gz`

**Note:** the P1m experiment in this evidence window covered SPYx, QQQx, TSLAx and AAPLx; NVDAx was not rerun under P1m because its local dataset was not staged on the VM at that point.
