# Valtide — Product Requirements Document

**Version:** 0.4  
**Last updated:** 20 Sep 2026  
**Status:** Public working specification

## 1. Product Summary

Valtide is an **independent oracle / model-validation layer for tokenized-equity collateral**.

It gives DeFi curators and lending-protocol risk teams an independent view of whether a production collateral valuation remains supported when traditional, tokenized and constructed references diverge.

Valtide does this through three core capabilities:

1. an independent challenger fair-value estimate,
2. calibrated uncertainty around that estimate,
3. validation logic that compares the production reference against independent market evidence.

Valtide is **not** a primary production oracle, lending protocol or automated LTV controller.

Its core product question is:

> **“Is the collateral valuation this protocol is relying on supported by independent evidence?”**

---

## 2. Primary User

### DeFi curator / lending-protocol risk team

The primary user is responsible for reviewing collateral assumptions and deciding whether a lending market remains appropriately configured.

Representative users include:

- lending-market curators,
- protocol risk councils,
- vault managers,
- RWA credit teams,
- independent risk-service providers.

### Core job to be done

> **“Give me an independent, explainable view of fair value, uncertainty and cross-market disagreement so I can validate my current collateral pricing assumptions.”**

### Relevant workflows

- periodic oracle / model validation,
- tokenized-equity collateral onboarding,
- investigation of unusual divergence,
- review of conservative or aggressive valuation policies,
- evidence gathering before parameter changes,
- post-event analysis after large off-hours moves.

---

## 3. Problem Statement

Tokenized equities can remain transferable and trade while the strongest traditional reference market is unavailable or lower quality.

At the same time, production systems increasingly use different approaches to value always-on equity exposure:

- traditional / session-aware equity feeds,
- constructed 24/7 indices,
- exchange-specific hybrid indices,
- tokenized-market prices,
- bounded or tolerance-based oracle logic.

This means a risk team can face situations where:

```text
Production collateral reference    $190
Pyth constructed reference         $185
Tokenized market                   $184
Other derivative reference         $186
```

The problem is no longer simply:

> “How do we create a weekend stock price?”

It is:

> **“Which valuation should we trust, how uncertain is that conclusion, and does the disagreement justify review?”**

---

## 4. Product Hypothesis

A specialized independent challenger layer can add value even when strong primary oracle infrastructure already exists.

Valtide tests whether:

1. tokenized-market price discovery and related signals contain useful independent information;
2. an independent challenger estimator can produce calibrated fair-value ranges;
3. cross-reference disagreement can identify periods when a production reference deserves review;
4. historical replay can make that validation auditable rather than purely judgmental.

This hypothesis is falsifiable.

If Valtide cannot add useful information beyond existing production controls, Pyth / OKX references, raw token prices and simple statistical baselines, the current product thesis should be reconsidered.

---

## 5. Value Proposition

Valtide does **not** promise to make protocols lend more.

A risk team may use Valtide to become either more aggressive or more conservative.

The value proposition is:

> **Independent evidence for collateral-valuation decisions.**

More specifically, Valtide should help a risk team answer:

- Is the current production reference consistent with independent evidence?
- How far is it from the challenger estimate?
- Is that deviation large relative to model uncertainty?
- Do tokenized and external markets agree with each other?
- Has a similar disagreement historically resolved toward the production reference or away from it?
- Is this an ordinary model difference or an exception worth investigating?

---

## 6. Product Principles

### 6.1 Independence over aggregation

Valtide should not simply average every available reference into a new oracle.

The challenger estimator must remain sufficiently independent for disagreement to be informative.

### 6.2 Uncertainty over false precision

A point estimate is not enough.

Valtide should expose prediction intervals and calibration evidence.

### 6.3 Evidence over policy automation

Valtide should show why a reference is supported or challenged.

It should not claim to know a universal correct LTV or automatically control protocol parameters.

### 6.4 Point-in-time correctness

Historical replay must use only data that would have been available at the observation timestamp.

### 6.5 Negative results are first-class results

If Pyth, the raw token price or a simple blend performs better, the product should show it.

---

## 7. MVP Asset Scope

### P0 — NVDAx, subject to data access

NVDAx is the preferred first research asset because:

- NVDA has meaningful single-name volatility,
- NVDAx is used in current tokenized-equity vault/lending products,
- Pyth launch materials included a 24/7 NVDA index,
- OKX supports an NVDA X-Perp,
- the asset provides several competing references for validation.

Historical Pyth / venue access should be verified before making the benchmark mandatory.

### P1 / fallback — SPYx

SPYx is strategically important because:

- it is directly relevant to tokenized-equity collateral,
- the underlying is highly liquid and diversified,
- OKX supports a SPY X-Perp,
- it provides a useful lower-idiosyncratic-risk comparison.

### Asset-selection rule

The MVP should prioritize **reliable historical data and point-in-time comparability** over attachment to a specific ticker.

---

## 8. Core Product Workflow

### Step 1 — Select asset and timestamp

The user selects a supported tokenized equity, such as NVDAx.

For live mode, Valtide uses the latest point-in-time snapshot.

For replay mode, the user selects a historical observation.

### Step 2 — Inspect the reference set

Valtide displays the major relevant references separately.

Example:

```text
Last trusted cash reference    $180.00
Production collateral price    $190.00
Tokenized market               $185.10
Pyth / constructed reference   $185.40
OKX / derivative reference     $186.00
```

Not every source will always be available.

### Step 3 — Run the independent challenger model

Example:

```text
Valtide fair value             $185.70
90% interval             $184.20–187.20
```

### Step 4 — Validate the production reference

Example:

```text
Production reference deviation    +2.32%
Standardized deviation              2.4σ
Validation status                 REVIEW
```

### Step 5 — Explain the disagreement

The interface should show:

- which sources agree,
- which source is an outlier,
- token/reference basis,
- Valtide residual premium/discount,
- reference age / market state,
- uncertainty regime,
- reason codes.

### Step 6 — Historical evidence

The user can reveal the later liquid-market benchmark and compare how each reference performed.

This is the primary credibility mechanism.

---

## 9. Core Outputs

The product should expose the following conceptual result fields.

### Observation context

- asset,
- timestamp,
- market/session state,
- last trusted underlying reference,
- age of trusted reference,
- production reference being validated,
- external reference set.

### Challenger valuation

- Valtide fair value,
- lower bound,
- upper bound,
- interval coverage target,
- model version.

### Basis / disagreement analysis

- observed token/reference move,
- model-implied move,
- residual token premium/discount,
- production-reference deviation,
- standardized deviation.

### Validation result

- `support`,
- `watch`,
- `review`,
- reason codes,
- optional evidence-agreement indicators.

### Important interpretation rule

The residual token premium/discount is **not automatically a liquidity premium, mispricing or arbitrage opportunity**.

It is the portion of the tokenized price not explained by the challenger estimate.

---

## 10. Public Interface / Dashboard

The MVP should remain focused around model validation rather than becoming a generic DeFi dashboard.

### View 1 — Validation Overview

Immediately answer:

1. What is the production collateral reference?
2. What are the independent market references?
3. What does Valtide estimate?
4. How uncertain is the estimate?
5. Is the production reference supported or challenged?

### View 2 — Reference Comparison

Show each reference separately rather than hiding disagreement in one composite score.

A compact visual should make it obvious when one reference is outside the independent evidence range.

### View 3 — Basis Analysis

Show:

- token/reference basis,
- model-implied move,
- residual premium/discount,
- source age / market session,
- available market-quality context.

### View 4 — Historical Replay

Reconstruct a point-in-time state and later reveal the evaluation benchmark.

### View 5 — Model Evidence

Show:

- MAE / RMSE,
- performance versus baselines,
- interval coverage,
- false challenge / missed challenge statistics where available,
- regime-specific performance.

---

## 11. Functional Requirements

### P0 — Data

- ingest tokenized-equity price history,
- ingest underlying equity/reference history,
- normalize timestamps and sessions,
- preserve source provenance,
- account for corporate actions / token multipliers where necessary,
- ingest at least one independent external constructed or derivative reference where accessible,
- support historical replay without look-ahead leakage.

### P0 — Quant

- implement naive baselines,
- implement an independent challenger estimator,
- generate calibrated uncertainty intervals,
- compute basis / residual analysis,
- compute reference deviation and validation status,
- run walk-forward evaluation,
- expose model/version metadata.

### P0 — Backend

- provide normalized market snapshots to the quant layer,
- expose current valuation / validation results,
- expose historical replay,
- expose backtest metrics,
- support publication of an approved validation snapshot to X Layer.

Exact service boundaries and API shapes are implementation contracts and may evolve as long as the public product semantics remain stable.

### P0 — Frontend

- Validation Overview,
- Reference Comparison,
- Basis Analysis,
- Historical Replay,
- Model Evidence,
- Onchain publication status.

### P0 — X Layer

Deploy a minimal contract that publishes the latest approved Valtide validation snapshot.

The contract is a machine-readable reference layer, not a production liquidation oracle.

---

## 12. Non-Goals

The MVP will not:

- replace Chainlink, Pyth or another production oracle,
- build a lending protocol,
- automatically change LTV / LLTV / caps,
- claim a universal correct LTV,
- execute trades or liquidations,
- claim causal identification of liquidity premium or mispricing,
- become a generic protocol risk dashboard,
- model the entire lending book in P0,
- predict long-horizon stock returns,
- support a large asset universe,
- hide negative benchmark results.

---

## 13. Historical Evaluation

### Required reference baselines

At minimum:

1. last trusted underlying / stale reference,
2. raw tokenized-equity price,
3. simple statistical blend,
4. Valtide challenger estimate.

Where data access allows:

5. Pyth 24/7 constructed index,
6. OKX X-Perp Index / Mark reference or another relevant continuous benchmark,
7. production collateral reference being validated.

### Ex-post benchmark

Preferred proxy:

> first 5–15 minute VWAP or robust midpoint after a sufficiently liquid underlying session becomes available.

This is an evaluation proxy, not proof of the exact unobservable fair value at the earlier timestamp.

---

## 14. Success Criteria

### Data success

- the selected asset has enough timestamp-aligned history to build point-in-time observations,
- source provenance is preserved,
- session transitions are correctly labeled,
- corporate actions do not contaminate returns,
- external comparator access is sufficient for meaningful testing.

### Quantitative success

Minimum evidence:

- Valtide improves on the stale-reference baseline,
- Valtide adds information beyond the raw token price or a simple blend,
- uncertainty intervals are reasonably calibrated.

Stronger evidence:

- Valtide is competitive with strong constructed references in defined regimes,
- or it provides useful independent disagreement signals even when another reference has similar point accuracy,
- validation alerts identify genuinely weak production-reference periods with acceptable false-positive rates.

### Product success

A risk professional should be able to understand:

- which reference is being validated,
- what independent sources say,
- what Valtide says,
- how uncertain Valtide is,
- why the status is `support`, `watch` or `review`,
- how the methodology performed historically.

---

## 15. Onchain Role

The onchain component exists to make an approved Valtide validation snapshot machine-readable on X Layer.

Conceptual flow:

```text
Market / oracle data
        ↓
Valtide challenger + validation engine
        ↓
Backend publisher
        ↓
ValtideValidationFeed.sol
        ↓
protocol / curator / agent can read
```

Minimum published state:

```text
asset
fairValue
lowerBound
upperBound
validationStatus
referenceDeviation
updatedAt
modelVersion
```

The contract must not present itself as a production-grade decentralized oracle guarantee.

---

## 16. Priority Scope

### P0 — Ship

- one primary asset with reliable data,
- point-in-time historical dataset,
- independent challenger estimator,
- uncertainty interval,
- production-reference validation,
- basis / residual analysis,
- external reference comparison,
- historical replay,
- backtest / validation evidence,
- API,
- focused web interface,
- minimal X Layer validation-feed contract.

### P1 — After P0 works

- SPYx or second asset,
- richer cross-market feature set,
- multiple production-reference adapters,
- alerts / webhooks,
- configurable validation thresholds,
- optional borrower-position / liquidation impact simulation.

### P2 — Stretch

- portfolio-level validation,
- protocol-specific adapters,
- scheduled onchain publication,
- MCP / agent access,
- broader tokenized-security coverage.

---

## 17. Key Risks

### Existing systems may already surface the same information

Kamino Scope, KRAF, Pyth and exchange indices are sophisticated.

**Response:** test incremental information rather than assuming whitespace.

### The challenger model may be weaker than incumbents

Pyth and OKX have stronger data access and production infrastructure.

**Response:** Valtide's differentiation is independent validation, not a claim that it is always the most accurate price source.

### Historical data may be too short

Tokenized-equity markets are new.

**Response:** keep the model simple, use walk-forward testing, report sample limitations and prioritize reproducibility.

### Validation may create noisy alerts

A challenger that flags everything is useless.

**Response:** evaluate false positives, missed challenges and regime-specific performance.

### The product may drift into generic risk analytics

Protocol exposure simulation is attractive but overlaps with mature incumbents.

**Response:** keep P0 centered on valuation / model validation.

---

## 18. Positioning

### Public positioning

> **Valtide is an independent oracle and model-validation layer for tokenized-equity collateral, helping DeFi risk teams determine whether production collateral valuations remain supported when traditional, tokenized and constructed markets diverge.**

### Short pitch

> **Independent validation for tokenized-equity collateral.**

### Technical thesis

> **Use an independent challenger model and calibrated uncertainty to turn cross-market price disagreement into an auditable validation signal.**

### What Valtide is not

> **Not another 24/7 stock oracle. Not a universal LTV engine. Not another lending protocol.**

---

## 19. Related Documents

- [`USER_MARKET_RESEARCH.md`](./USER_MARKET_RESEARCH.md)
- [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`METHODOLOGY.md`](./METHODOLOGY.md)
