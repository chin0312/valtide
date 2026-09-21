# Valtide — Validation & Valuation Methodology

**Version:** 0.2  
**Last updated:** 20 Sep 2026  
**Status:** Public research methodology

## 1. Objective

Valtide is designed to validate tokenized-equity collateral valuations using an independent quantitative methodology.

The methodology has two layers:

1. **Challenger valuation** — estimate a latent current equity value and uncertainty using point-in-time market information;
2. **Reference validation** — test whether the reference under test is consistent with the challenger estimate and other independent evidence.

The reference under test is the generic reference Valtide validates. In the primary product use case, it is a production collateral reference; when that reference is unavailable during the hackathon, it may be a reconstructed protocol valuation methodology, a Chainlink reference, an OKX bounded/index reference, or another selected reference.

The product is therefore not asking only:

> “What is the true price?”

It is asking:

> **“Is the price methodology currently used for collateral valuation still supported by independent evidence?”**

This is a nowcasting and model-validation problem, not a long-horizon equity forecast.

---

## 2. Research Questions

### Primary question

For an observation timestamp `t` during a closed, fragmented or lower-quality market period:

> **Is the reference under test supported by independent evidence?**

In the primary real-world workflow, the reference under test is the production collateral reference.

### Supporting quantitative questions

1. Can tokenized-market information improve fair-value estimation beyond the last trusted underlying reference?
2. Does the challenger estimate add information beyond simply using the raw tokenized-market price?
3. How does the challenger perform relative to constructed references such as Pyth or exchange indices such as OKX X-Perps when comparable data are available?
4. Are challenger uncertainty intervals calibrated?
5. When Valtide flags the reference under test as an outlier, does later liquid-market evidence support that challenge often enough to be useful?

---

## 3. Conceptual Model

Let:

- `R0` = last trusted underlying/reference price before the target period,
- `Tt` = tokenized-equity price at observation time `t`,
- `Xt` = independent point-in-time market features,
- `Ft` = Valtide challenger fair-value estimate,
- `[Lt, Ut]` = Valtide prediction interval,
- `Pt` = reference under test at timestamp `t`, preferably the production collateral reference,
- `Ej,t` = external reference `j` such as Pyth / OKX / Chainlink,
- `B` = later liquid-market benchmark used only for evaluation.

The system intentionally distinguishes:

```text
challenger estimate Ft
        from
reference under test Pt
        from
external evidence Ej,t
```

The purpose is not to average these into one opaque number. The disagreement itself is an output.

---

## 4. Challenger Valuation Layer

### 4.1 Target

The challenger model estimates the latent current value of the underlying equity given information available by timestamp `t`.

Because latent fair value is not directly observable while the strongest market is closed, the estimate must be treated as a model output with uncertainty.

### 4.2 Return representation

Use log returns where practical.

Tokenized move relative to last trusted reference:

```text
r_token(t) = ln(Tt / R0)
```

The model predicts a latent return:

```text
r_hat(t) = f(r_token(t), Xt)
```

Convert back to price:

```text
Ft = R0 × exp(r_hat(t))
```

### 4.3 Core interpretation

Valtide does not assume:

```text
Tt = true fair value
```

and does not assume:

```text
R0 = true fair value
```

Instead, the tokenized market is treated as a potentially informative but noisy signal.

---

## 5. V0 Challenger Model Strategy

The first model should be deliberately simple and auditable.

Recommended first estimator family:

> **regularized linear / shrinkage regression with market-regime interactions**

Conceptually:

```text
latent return
=
β0
+ β1 × tokenized return
+ β2...k × independent cross-market features
+ regime interactions
+ error
```

Ridge regression is a reasonable initial implementation because:

- the historical sample is short,
- feature count should remain small,
- the market is structurally changing,
- overfitting is a larger risk than under-modeling.

A Kalman filter, state-space model or more complex ML model should only be added if it produces clear walk-forward improvement.

Model complexity is not itself a differentiation.

---

## 6. Candidate Features

Every feature must have been observable by timestamp `t`.

### 6.1 Required features

#### Tokenized-equity return

```text
ln(Tt / R0)
```

This is the core tokenized-market price-discovery signal.

#### Time since trusted reference

```text
t - timestamp(R0)
```

A 20-minute-old reference and a 30-hour-old reference should not be treated equivalently.

#### Market / session regime

Examples:

- regular,
- extended,
- overnight,
- weekend / closed,
- unknown / degraded.

### 6.2 Candidate market-quality features

Subject to reliable data access:

- token volume,
- USD volume,
- bid/ask spread,
- order-book depth,
- tokenized-market liquidity,
- short-horizon realized volatility,
- distance from recent token VWAP,
- cross-venue token-price dispersion.

Market-quality features may affect:

- the point estimate,
- uncertainty,
- or both.

Their role should be empirical rather than assumed.

### 6.3 Candidate independent cross-market features

Subject to point-in-time availability:

- broad equity proxy,
- sector / semiconductor proxy,
- equity futures,
- related tokenized-equity basket,
- other independently observed derivative signals.

---

## 7. Independence Policy

The challenger model is valuable only if it is meaningfully independent from the reference under test it validates.

### 7.1 Core benchmark model

If Valtide is being compared against Pyth or OKX X-Perp as external references:

- do not use the final Pyth constructed index as a model feature,
- do not use the final OKX X-Perp Index Price as a model feature,
- do not mechanically transform the reference under test into the output.

### 7.2 External evidence after inference

After `Ft` is produced, Valtide may compare:

- `Pt` reference under test,
- Pyth constructed reference,
- OKX X-Perp reference,
- Chainlink reference,
- tokenized-market price,
- other evidence.

### 7.3 Augmented experiments

A second experimental model may use Pyth or OKX as a feature, but it must be labeled separately and must not be presented as the independent challenger model.

---

## 8. Uncertainty Estimation

A point estimate without uncertainty is insufficient for validation.

### Preferred V0 approach

Construct empirical prediction intervals using time-ordered out-of-sample residuals.

Implementation options, from simplest to more sophisticated:

1. rolling residual quantiles,
2. time-aware conformal prediction,
3. conditional variance / heteroskedastic regression if the sample supports it.

Example:

```text
Valtide fair value    $185.70
90% interval          $184.20 – $187.20
```

### Calibration objective

For a nominal 90% interval:

```text
empirical coverage ≈ 90%
```

Coverage and interval width should both be reported.

An interval that is extremely wide can achieve good coverage while being operationally unhelpful.

---

## 9. Confidence Presentation

The prediction interval is the primary uncertainty output.

If the UI exposes a 0–100 confidence score, it should be derived from calibrated uncertainty rather than interpreted as a probability that the price is “correct.”

Possible presentation variable:

```text
relativeIntervalWidth = (Ut - Lt) / Ft
```

This can be mapped against the historical distribution for that asset and regime.

Meaning:

> **“This estimate is relatively precise / imprecise compared with Valtide's historical observations.”**

Not:

> “There is a 78% probability that $185.70 is correct.”

---

## 10. Token Basis Analysis

For the last trusted reference `R0`, tokenized price `Tt`, and Valtide fair value `Ft`:

### Observed token move

```text
observedTokenMove = Tt / R0 - 1
```

### Model-implied move

```text
modelImpliedMove = Ft / R0 - 1
```

### Residual token premium / discount

```text
residual = Tt / Ft - 1
```

Example:

```text
R0 = $180.00
Tt = $188.00
Ft = $185.70

Observed token move       +4.44%
Model-implied move        +3.17%
Residual premium          +1.24%
```

### Interpretation rule

The residual is descriptive, not causal.

Do not automatically call it:

- liquidity premium,
- mispricing,
- manipulation,
- arbitrage opportunity.

It means only:

> **the tokenized market is trading above or below the independent challenger estimate by this amount.**

---

## 11. Reference-Under-Test Validation

Let `Pt` be the reference under test being validated. In the primary product use case, `Pt` is the production collateral reference.

### 11.1 Raw reference deviation

```text
referenceDeviation = Pt / Ft - 1
```

This shows the difference between the reference-under-test valuation and the independent challenger center.

### 11.2 Standardized deviation

A validation decision should account for uncertainty.

Conceptually:

```text
z_ref = (Pt - Ft) / uncertaintyScale_t
```

where `uncertaintyScale_t` is derived from the calibrated predictive distribution.

A $2 difference is much more meaningful when the expected uncertainty is $0.50 than when it is $8.

### 11.3 Prediction-interval test

A simple interpretable check is whether `Pt` lies:

- inside the core prediction interval,
- near an interval boundary,
- outside the interval.

This can be combined with standardized deviation and cross-source evidence.

---

## 12. Cross-Reference Evidence

Valtide should preserve each external reference separately.

Possible references:

```text
reference under test
production oracle / collateral reference
Pyth 24/7 index
OKX X-Perp index
Chainlink equity reference
raw tokenized market
```

### Evidence questions

- Do independent references cluster around Valtide?
- Is the reference under test the outlier?
- Is the tokenized market the outlier?
- Are all references widely dispersed?
- Are external references stale or low quality?

### Important rule

Cross-source agreement is not proof of truth.

Multiple systems can share data or methodology.

Source dependence should be documented where known.

---

## 13. Validation Status

The product may summarize the result as:

```text
SUPPORT
WATCH
REVIEW
```

### Example initial policy

A provisional V0 policy may combine:

- standardized reference-under-test deviation,
- whether `Pt` lies inside the Valtide interval,
- availability and agreement of external evidence,
- data-quality / staleness flags.

Illustrative standardized thresholds:

```text
|z_ref| < 1.0          SUPPORT
1.0 ≤ |z_ref| < 2.0   WATCH
|z_ref| ≥ 2.0          REVIEW
```

These are research defaults, not financial-risk standards.

They must be calibrated and may change after observing real residual distributions.

### Reason codes

Examples:

```text
REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL
TOKEN_AND_CHALLENGER_AGREE
EXTERNAL_REFERENCES_AGREE
EXTERNAL_REFERENCES_DISAGREE
UNDERLYING_REFERENCE_STALE
MODEL_UNCERTAINTY_HIGH
TOKEN_MARKET_QUALITY_LOW
COMPARATOR_UNAVAILABLE
```

Reason codes make the validation status auditable.

---

## 14. Historical Observation Design

The unit of analysis is a **point-in-time observation**.

For each observation:

```text
1. identify last trusted underlying reference R0
2. choose observation timestamp t
3. collect only information available by t
4. construct Market Snapshot
5. run challenger model → Ft, [Lt, Ut]
6. collect production / external references available by t
7. run validation engine
8. later attach evaluation benchmark B
9. score both valuation and validation quality
```

Potential regimes:

- regular-to-extended transition,
- overnight,
- Friday close to weekend,
- pre-reopen,
- high token/reference divergence,
- high-volatility news periods.

---

## 15. Ex-Post Evaluation Benchmark

True fair value at timestamp `t` is unobservable.

Valtide therefore uses a later liquid-market price as an **evaluation proxy**, not ground truth.

Preferred proxy:

> first 5–15 minute VWAP or robust midpoint after the underlying enters a sufficiently liquid session.

### Why not the first print?

- opening prints / auctions can be noisy,
- a single trade may not reflect executable consensus,
- a short VWAP or midpoint is more robust.

### Timing limitation

Information may arrive between timestamp `t` and the later benchmark.

Therefore:

- evaluate multiple observation horizons,
- separately report observations close to reopening,
- do not claim that the later benchmark proves the exact fair value that existed earlier.

---

## 16. Fair-Value Baselines

### Baseline A — stale reference

```text
estimate = R0
```

Tests whether no off-hours inference is needed.

### Baseline B — raw tokenized price

```text
estimate = Tt
```

Tests whether the tokenized market itself already captures all useful information.

### Baseline C — simple blend

```text
estimate = w × Tt + (1-w) × R0
```

where `w` is estimated using past training data only.

If Valtide cannot beat a simple blend out of sample, added model complexity is not justified.

### Baseline D — Pyth 24/7 index

Use when historical access is available for the selected asset.

### Baseline E — OKX X-Perp reference

Use when comparable historical Index / Mark data are accessible.

These strong baselines are intentionally difficult. Valtide should not define success only against a stale close.

---

## 17. Valuation Metrics

### Point-estimate accuracy

- MAE,
- RMSE,
- median absolute percentage error,
- mean absolute log error.

### Relative performance

- percentage of observations closer than stale reference,
- percentage closer than raw token price,
- percentage closer than simple blend,
- percentage closer than Pyth / OKX where available,
- relative error reduction.

### Uncertainty quality

- empirical interval coverage,
- average interval width,
- interval score where practical,
- coverage by regime.

---

## 18. Validation Metrics

Point-estimate accuracy alone is not enough because Valtide's product is model validation.

Define an ex-post **reference-under-test error event** using the later benchmark `B` and a tolerance appropriate to the experiment. In the primary product use case, this is a production-reference error event.

Example research label:

```text
referenceWeak_t = 1
if |Pt - B| exceeds a predefined / data-calibrated tolerance
```

Then evaluate whether Valtide's `WATCH` / `REVIEW` states identified those events.

Potential metrics:

- challenge precision,
- challenge recall,
- false-positive rate,
- false-negative rate,
- average later correction following a challenge,
- performance by regime.

Thresholds must be defined using training / validation data, not selected after seeing the final test results.

### Important limitation

A later benchmark may disagree with the reference under test `Pt` because new information arrived after `t`.

Therefore these classification metrics are diagnostic, not proof of oracle fault.

---

## 19. False-Liquidation vs Delayed-Liquidation Context

Production lending systems may rationally prefer conservative references.

A constructed off-hours price can react faster to new information, but if that constructed price is wrong it may create false-liquidation risk.

A stale / bounded reference can reduce synthetic-price liquidation risk but increase delayed-liquidation and gap risk.

Valtide's P0 methodology does **not** claim to solve the protocol's entire trade-off.

Instead it quantifies:

- how far production valuation is from independent evidence,
- how uncertain that evidence is,
- how similar disagreement behaved historically.

The protocol retains the policy decision.

---

## 20. Optional Protocol-Impact Layer — P1

If reliable protocol-position data become available, Valtide may later simulate the consequence of alternative valuation scenarios.

Examples:

```text
positions crossing LLTV under $X reference
collateral value affected
estimated liquidation notional
scenario shortfall
```

This would connect model validation to protocol impact.

It is intentionally **not required for P0** because it moves Valtide toward broader protocol-risk analytics where strong incumbents already exist.

---

## 21. Train / Test Design

Random train-test splits are inappropriate for this time-series problem.

Use:

> **walk-forward / expanding-window evaluation**

Example:

```text
Train: earliest observations → date A
Test: next block

Expand training window
Test: next block

Repeat
```

All feature engineering, hyperparameter selection and threshold calibration must use past data only.

---

## 22. Data Quality Controls

### Timestamp normalization

Normalize timestamps to UTC.

### Point-in-time availability

A feature is invalid if it was not observable by timestamp `t`.

### Corporate actions

Adjust splits, dividends / multipliers and token rebases where required so mechanical adjustments are not mistaken for economic returns.

### Missing data

Do not silently forward-fill long gaps.

### Source provenance

Record the source of every observation and reference.

### Asynchronous observations

Retain source age and define deterministic alignment rules.

### Source dependence

Where external references share upstream data, note the dependence instead of treating them as fully independent votes.

---

## 23. MVP Data Sources

### Tokenized market

Potential sources:

- [OKX OnchainOS RWA Token List](https://web3.okx.com/onchainos/dev-docs/market/market-rwa-token)
- [OKX Historical Candlesticks](https://web3.okx.com/onchainos/dev-docs/market/market-candlesticks-history)
- [xStocks Developer Docs](https://docs.xstocks.fi/developers)

### Underlying / session context

Potential sources include accessible U.S. equity historical data and Chainlink current/reference products.

- [Chainlink — 24/5 U.S. Equities Streams](https://chain.link/blog/chainlink-24-5-us-equities-streams)

### Constructed / derivative comparators

- [Pyth Indices](https://www.pyth.network/products/pyth-indices)
- [Pyth Pro History API](https://docs.pyth.network/price-feeds/pro/api/history)
- [OKX — Stock and Commodity X-Perps](https://www.okx.com/en-us/help/how-do-stock-and-commodity-x-perps-work)

Comparator availability must be verified for the chosen asset and historical period.

---

## 24. Go / No-Go Tests

### Go test A — challenger signal exists

Proceed if a simple point-in-time-correct challenger model adds information beyond:

- stale reference,
- raw token price,
- simple blend.

### Go test B — uncertainty is useful

Proceed if prediction intervals are reasonably calibrated and not so wide that validation becomes meaningless.

### Go test C — validation adds information

Proceed if `WATCH` / `REVIEW` states identify meaningful disagreement events with acceptable false-positive behavior.

### Stronger evidence

The thesis becomes materially stronger if Valtide:

- competes with strong constructed references in specific regimes,
- or produces useful validation signals even when an incumbent reference has similar point accuracy.

### No-go / pivot conditions

Reconsider the thesis if:

- data quality is insufficient,
- raw token price or simple blend consistently dominates,
- Pyth / OKX references dominate without useful independent residual information,
- challenge alerts are mostly noise,
- performance disappears out of sample,
- intervals cannot be calibrated,
- a production risk team would not use the evidence.

---

## 25. Research Integrity

Valtide should report negative evidence.

Do not:

- cherry-pick weekends,
- hide periods where incumbent references win,
- tune challenge thresholds on the final test set,
- call residual basis “mispricing” without evidence,
- claim production-oracle reliability from a short sample,
- claim causal explanation when the model only shows disagreement.

The strongest credible result may be:

> **“Valtide adds measurable validation value in these specific market regimes, and it can identify when its own evidence is too uncertain to challenge the reference under test.”**

That is more defensible than claiming Valtide is always the best price source.

---

## 26. Methodology Summary

Valtide's methodology can be summarized as:

```text
Point-in-time market data
        ↓
Independent challenger model
        ↓
Fair value + calibrated uncertainty
        ↓
Compare with production + external references
        ↓
Quantify disagreement
        ↓
SUPPORT / WATCH / REVIEW
        ↓
Historical replay and out-of-sample validation
```

The key methodological principle is:

> **Valtide does not need to replace the production oracle to be useful. It needs to independently detect when the production valuation is well supported, weakly supported or materially challenged.**
