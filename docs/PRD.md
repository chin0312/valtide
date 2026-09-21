# Valtide — Product Requirements Document

**Version:** 0.5  
**Last updated:** 20 Sep 2026  
**Status:** Public working specification

## 1. Product Summary

Valtide is an **independent collateral-valuation control layer for tokenized equities on X Layer**.

It gives DeFi curators and lending-protocol risk teams an independent view of whether a production collateral valuation remains supported when traditional, tokenized and constructed references diverge.

Valtide does this through four connected capabilities:

1. an independent challenger fair-value estimate,
2. calibrated uncertainty around that estimate,
3. validation logic that produces a standardized Evidence State, and
4. an X Layer control interface through which a curator-configured policy can consume that evidence.

Valtide is **not** a primary production oracle, lending protocol or automated LTV controller. It does not choose a universal policy action or automatically liquidate positions.

Its core product question is:

> **“Is the collateral valuation this protocol is relying on supported by independent evidence?”**

In this document, the **reference under test** is the generic reference Valtide validates. In the primary product use case, it is the production collateral reference; when a live production reference is unavailable during the hackathon, it may be a reconstructed protocol valuation methodology, a Chainlink reference, an OKX bounded/index reference, or another selected reference.

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

> **“When I manage a lending market using tokenized equities as collateral and my reference price becomes stale, uncertain or disagrees with other markets, help me independently determine whether that valuation is still supported by market evidence, so I can decide whether to continue normal operations, investigate the discrepancy or restrict additional risk exposure — and enforce that policy consistently onchain.”**

The product is structured around four jobs:

```text
VALIDATE
Is the reference I rely on still supported?

DIAGNOSE
Why are the reference, tokenized market and independent evidence disagreeing?

TRIAGE
Is the evidence strong enough to support the reference, challenge it, or is the result inconclusive?

GUARD
How should my own predefined risk policy respond to that evidence?
```

Valtide performs the first three jobs directly. For the fourth, Valtide provides standardized onchain evidence and policy infrastructure while the curator or consuming protocol defines the actual policy action.

> **Valtide determines the Evidence State. The curator or protocol determines the Policy Action.**

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

Valtide should show why a reference is supported, inconclusive or challenged.

It should not claim to know a universal correct LTV or automatically control protocol parameters. The consuming curator or protocol chooses how each Evidence State maps to its own Policy Action.

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

### Step 4 — Validate the reference under test

In the primary use case, the reference under test is the production collateral reference. During the hackathon, it may instead be a reconstructed or selected reference used for validation.

Example:

```text
Reference-under-test deviation    +2.32%
Standardized deviation              2.4σ
Evidence State                  CHALLENGED
```

### Step 5 — Triage and explain the disagreement

Valtide assigns one Evidence State:

- `SUPPORTED` — available independent evidence does not provide a material reason to challenge the reference under test;
- `INCONCLUSIVE` — evidence is not sufficiently strong or consistent to support or materially challenge the reference; or
- `CHALLENGED` — the reference under test is materially inconsistent with sufficiently strong independent evidence.

These are evidence semantics, not action recommendations. Valtide determines the Evidence State. The curator or protocol determines the Policy Action.

The interface should show:

- which sources agree,
- which source is an outlier,
- token/reference basis,
- Valtide residual premium/discount,
- reference age / market state,
- uncertainty regime,
- reason codes.

The human user can then decide whether to continue normal operations, investigate the discrepancy, or restrict additional risk exposure.

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
- reference under test being validated,
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
- reference-under-test deviation,
- standardized deviation.

### Validation result

- Evidence State: `SUPPORTED`, `INCONCLUSIVE` or `CHALLENGED`,
- reason codes,
- optional evidence-agreement indicators.

### Policy interface

Policy Actions are configured by the curator or consuming protocol rather than generated by the quant model. Example actions include:

```text
ALLOW
MONITOR
REQUIRE_REVIEW
RESTRICT_NEW_RISK
```

The mapping is configurable. For example, one protocol may map `INCONCLUSIVE` to `MONITOR`, while another may map it to `REQUIRE_REVIEW`.

### Important interpretation rule

The residual token premium/discount is **not automatically a liquidity premium, mispricing or arbitrage opportunity**.

It is the portion of the tokenized price not explained by the challenger estimate.

---

## 10. Public Interface / Dashboard

The MVP should remain focused around model validation rather than becoming a generic DeFi dashboard.

### View 1 — Validation Overview

Immediately answer:

1. What is the reference under test, preferably the production collateral reference?
2. What are the independent market references?
3. What does Valtide estimate?
4. How uncertain is the estimate?
5. What is the Evidence State?
6. What Policy Action would the configured policy return?

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

The dashboard serves the human decision-maker. It should explain the Evidence State and show the configured Policy Action separately rather than presenting the action as a model output.

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
- compute reference deviation and Evidence State,
- abstain with `INCONCLUSIVE` when evidence quality or uncertainty is insufficient,
- run walk-forward evaluation,
- expose model/version metadata.

### P0 — Backend

- provide normalized market snapshots to the quant layer,
- expose current valuation / validation results,
- expose historical replay,
- expose backtest metrics,
- support publication of an approved validation attestation to X Layer,
- expose configured Policy Action evaluation separately from the Evidence State.

Exact service boundaries and API shapes are implementation contracts and may evolve as long as the public product semantics remain stable.

### P0 — Frontend

- Validation Overview,
- Reference Comparison,
- Basis Analysis,
- Historical Replay,
- Model Evidence,
- Evidence State and Policy Action,
- X Layer Registry / Risk Guard status.

### P0 — X Layer

The intended MVP requires an onchain control flow from validation through policy evaluation and a working consumer:

```text
offchain validation
        ↓
onchain validation attestation
        ↓
onchain policy evaluation
        ↓
working consumer flow
```

P0 includes:

- `ValtideValidationRegistry.sol` for auditable validation attestations;
- `ValtideRiskGuard.sol` for curator-configured Policy Action evaluation; and
- a minimal `DemoCollateralVault.sol` reference consumer demonstrating composability.

The contracts are a machine-readable control layer, not a production liquidation oracle or lending protocol.

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
7. reference under test, preferably the production collateral reference.

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
- Evidence State challenges identify genuinely weak production-reference periods with acceptable false-challenge rates.

### Product success

A risk professional should be able to understand:

- which reference is being validated,
- what independent sources say,
- what Valtide says,
- how uncertain Valtide is,
- why the Evidence State is `SUPPORTED`, `INCONCLUSIVE` or `CHALLENGED`,
- what Policy Action the configured policy returns,
- how the methodology performed historically.

---

## 15. Onchain Role

The onchain component is a required part of the intended OKX Dev Day Build a Market MVP. It turns an approved offchain validation result into an auditable Evidence State and evaluates a Policy Action configured by the curator or consuming protocol.

The principle is:

> **Thin computation, strong protocol interface.**

Conceptual flow:

```text
Market / oracle data
        ↓
Valtide challenger + validation engine
        ↓
Backend publisher
        ↓
ValtideValidationRegistry.sol
        ↓
ValtideRiskGuard.sol
        ↓
DemoCollateralVault.sol / protocol / curator / agent
```

### Evidence State

The Registry stores one of:

```text
SUPPORTED
INCONCLUSIVE
CHALLENGED
```

These are evidence semantics, not policy recommendations. Valtide determines the Evidence State. The curator or protocol determines the Policy Action.

### Minimum published state

```text
asset
referenceId
referencePriceE8
fairValueE8
lowerBoundE8
upperBoundE8
referenceDeviationBps
evidenceState
evidenceHash
modelVersion
observedAt
publishedAt
validUntil
```

The asset remains the mapping key; `referenceId` identifies the reference under test. `evidenceHash` commits the attestation to the corresponding offchain evidence, normalized observation and model result without claiming that a hash makes the offchain data objectively correct.

### Policy Action

The Risk Guard evaluates a curator-configured mapping such as:

```text
Evidence State       Example protocol policy
------------------------------------------------
SUPPORTED            ALLOW
INCONCLUSIVE         REQUIRE_REVIEW
CHALLENGED           RESTRICT_NEW_RISK
STALE ATTESTATION    REQUIRE_REVIEW
```

Another protocol may choose `INCONCLUSIVE → MONITOR`. No single mapping is universal.

### Conceptual consumers

`DemoCollateralVault.sol` is a reference consumer demonstrating that an X Layer application can read the Registry and Risk Guard without embedding Valtide's statistical model. Its intended demo behavior is:

```text
SUPPORTED
→ new risk allowed

INCONCLUSIVE
→ policy may require review

CHALLENGED
→ policy may restrict new risk
```

The demo consumer is not a production protocol. The MVP should prefer restricting new exposure over automatically liquidating existing borrowers.

### Boundaries

Offchain components perform:

- market-data normalization,
- feature engineering,
- challenger estimation,
- uncertainty calibration,
- Evidence State generation,
- historical backtesting.

X Layer components provide:

- validation attestation,
- provenance commitment,
- timestamps and freshness,
- Evidence State availability,
- curator-configured Policy Action evaluation,
- consumer-facing risk controls.

The contract layer must not:

- calculate the model onchain,
- control user funds,
- set universal LTVs,
- liquidate positions,
- claim production-oracle guarantees.

---

## 16. Priority Scope

### P0 — Ship

- one primary asset with reliable data,
- point-in-time historical dataset,
- independent challenger estimator,
- uncertainty interval,
- reference-under-test validation,
- basis / residual analysis,
- external reference comparison,
- historical replay,
- backtest / validation evidence,
- Evidence State generation with explicit abstention,
- API,
- focused web interface,
- X Layer `ValtideValidationRegistry.sol`,
- X Layer `ValtideRiskGuard.sol`,
- working `DemoCollateralVault.sol` reference consumer,
- end-to-end attestation and policy-evaluation demo.

### P1 — After P0 works

- SPYx or second asset,
- richer cross-market feature set,
- multiple reference-under-test adapters,
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

### Evidence states may be noisy or too often inconclusive

A validation system that challenges everything or abstains from everything is useless.

**Response:** evaluate decision coverage, abstention rate, false challenges, false support and regime-specific performance.

### The product may drift into generic risk analytics

Protocol exposure simulation is attractive but overlaps with mature incumbents.

**Response:** keep P0 centered on valuation / model validation.

---

## 18. Positioning

### Public positioning

> **Valtide is an independent collateral-valuation control layer for tokenized equities on X Layer, helping DeFi risk teams determine whether a reference under test is supported, inconclusive or materially challenged when traditional, tokenized and constructed markets diverge.**

### Short pitch

> **Validate the reference. Understand the evidence. Enforce your own risk policy onchain.**

### Technical thesis

> **Use an independent challenger model and calibrated uncertainty to turn cross-market price disagreement into an auditable Evidence State and configurable X Layer control.**

### What Valtide is not

> **Not another 24/7 stock oracle. Not a universal LTV engine. Not another lending protocol. Not an automatic liquidation engine.**

---

## 19. Related Documents

- [`USER_MARKET_RESEARCH.md`](./USER_MARKET_RESEARCH.md)
- [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`METHODOLOGY.md`](./METHODOLOGY.md)
