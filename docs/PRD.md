# Valtide — Product Requirements Document

**Version:** 0.5  
**Status:** Product requirements reference; see `docs/PRODUCT_SEMANTICS.md` for the current implementation contract.

This document retains early product hypotheses and planning notes. Sections
labelled as future work or historical evaluation are not statements of current
deployment scope.

## 1. Product Summary

Valtide is a **validation layer for tokenized equity collateral**.

It helps DeFi curators and lending-protocol risk teams assess whether an
observed xStock price has enough supporting evidence for a collateral-risk
decision. It does not claim to discover an exact “true price.”

Valtide does this through four connected capabilities:

1. a model-based challenger Fair Value estimate,
2. calibrated uncertainty around that estimate,
3. validation logic that produces a standardized Evidence State, and
4. an X Layer control interface through which a curator-configured policy can consume that evidence.

Valtide is **not** a primary production oracle, lending protocol or automated LTV controller. It does not choose a universal policy action or automatically liquidate positions.

Its core product question is:

> **“Does the observed xStock price have enough supporting evidence for this collateral-risk decision?”**

Observed xStock is the validation target and is assimilated by P1a-C before it
emits Valtide Fair Value and the Valuation Range. Their disagreement is
model-based challenger evidence, not two independent market observations.
X-Perp is separately sourced second-market evidence. The Underlying Anchor is
model context and is not a same-time Evidence State voter. The curator or
protocol defines Policy Action, and the consuming protocol owns enforcement.

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

> **“When I manage a lending market using tokenized equities as collateral and the observed xStock price becomes uncertain or disagrees with other evidence, help me assess whether it has enough support for a collateral-risk decision, so I can decide whether to continue normal operations, investigate the discrepancy or restrict additional risk exposure — and have the consuming application apply my policy consistently onchain.”**

The product is structured around four jobs:

```text
VALIDATE
Is the reference I rely on still supported?

DIAGNOSE
Why do Observed xStock, Valtide Fair Value, and separately sourced X-Perp differ?

TRIAGE
Is the evidence strong enough to support the reference, challenge it, or is the result inconclusive?

GUARD
How should my own predefined risk policy respond to that evidence?
```

Valtide performs the first three jobs directly. For the fourth, Valtide provides standardized onchain evidence and policy infrastructure while the curator or consuming protocol defines the actual policy action. The consumer contract enforces the resulting action.

> **Valtide determines the Evidence State. The curator or protocol determines the Policy Action. The consumer enforces the resulting action.**

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

A specialized model-based challenger layer can add value even when strong primary oracle infrastructure already exists.

Valtide tests whether:

1. tokenized-market price discovery and related signals contain useful incremental information;
2. a challenger estimator can produce calibrated Fair Value ranges;
3. cross-reference disagreement can identify periods when a production reference deserves review;
4. historical replay can make that validation auditable rather than purely judgmental.

This hypothesis is falsifiable.

If Valtide cannot add useful information beyond existing production controls, Pyth / OKX references, raw token prices and simple statistical baselines, the current product thesis should be reconsidered.

---

## 5. Value Proposition

Valtide does **not** promise to make protocols lend more.

A risk team may use Valtide to become either more aggressive or more conservative.

The value proposition is:

> **Evidence for collateral-risk decisions.**

More specifically, Valtide should help a risk team answer:

- Does Observed xStock have enough supporting evidence for this decision?
- How far is it from the challenger estimate?
- Is that deviation large relative to model uncertainty?
- Do tokenized and external markets agree with each other?
- Has a similar disagreement historically resolved toward the production reference or away from it?
- Is this an ordinary model difference or an exception worth investigating?

---

## 6. Product Principles

### 6.1 Declared evidence roles over aggregation

Valtide should not simply average every available reference into a new oracle.
In the current profile, Observed xStock is both the validation target and an
input assimilated by P1a-C, so their disagreement is model-based challenger
evidence. X-Perp is separately sourced market evidence; these roles must not be
presented as three independent market votes.

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

## 7. Current Asset Scope

The current operational product assets are:

| Asset | Model | Operational | Historical replay | X Layer binding |
|---|---|---:|---:|---:|
| NVDAx | P1a-C v0.2.0 | Yes | Yes | Yes |
| SPYx | P1a-C v0.3.0 | Yes | Yes | Yes |
| AAPLx | P1a-C v0.3.0 | Yes | Yes | Yes |

QQQx remains research-only and is not exposed through the public HTTP API;
TSLAx remains research-only. Future asset expansion should prioritize
**reliable historical data and point-in-time comparability** over attachment
to a specific ticker.

---

## 8. Core Product Workflow

### Step 1 — Select asset and timestamp

The user selects a supported tokenized equity, such as NVDAx.

For live mode, Valtide uses the latest point-in-time snapshot.

For replay mode, the user selects a historical observation.

### Step 2 — Inspect the reference set

Valtide displays the major relevant references separately.

In the current product, Observed xStock is the validation target. P1a-C
assimilates that observation and emits a model-based challenger estimate;
exact-time X-Perp supplies separately sourced market evidence. The model and
target are not two independent market observations.

Example:

```text
Observed xStock                 $185.10
Valtide Fair Value              $185.70
Valuation Range                 $184.20–187.20
X-Perp                          $186.00
Underlying Anchor               $180.00
```

Not every source will always be available.

### Step 3 — Run the P1a-C model-based challenger

Example:

```text
Valtide fair value             $185.70
90% interval             $184.20–187.20
```

### Step 4 — Validate the observed xStock

The current unified profile validates Observed xStock using its frozen
P1a-C/xStock disagreement band, required source/model quality checks, and
exact-time X-Perp evidence. P1a-C has already assimilated the current xStock
input, so their disagreement is model-based challenger evidence. X-Perp is the
separately sourced market comparison.

Example:

```text
xStock / model disagreement       reported by detector
X-Perp direction                  reported as source evidence
Evidence State                    backend-owned result
```

### Step 5 — Triage and explain the disagreement

Valtide assigns one Evidence State:

- `SUPPORTED` — the frozen SUPPORT band applies, exact-time X-Perp is healthy and available, and quality checks pass;
- `INCONCLUSIVE` — evidence is not sufficiently strong or consistent to support or materially challenge the reference; or
- `CHALLENGED` — the frozen REVIEW band applies and exact-time X-Perp is closer to P1a-C than to Observed xStock, with quality checks passing.

The frozen `SUPPORT`, `WATCH`, and `REVIEW` detector bands are not aliases for
Evidence States. WATCH maps to `INCONCLUSIVE`; REVIEW with X-Perp siding with
xStock also remains `INCONCLUSIVE`. Missing, stale, ambiguous, or quality-gated
evidence fails closed to `INCONCLUSIVE`.

These are evidence semantics, not action recommendations. Valtide determines the Evidence State. The curator or protocol determines the Policy Action. The consumer enforces the resulting action.

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
- Observed xStock, the current validation target,
- Valtide Fair Value and Valuation Range,
- Underlying Anchor and its age, as model context,
- separately sourced X-Perp evidence when available.

### Challenger valuation

- Valtide fair value,
- lower bound,
- upper bound,
- interval coverage target,
- model version.

### Basis / disagreement analysis

- observed xStock move,
- model-implied move,
- residual token premium/discount,
- xStock/model disagreement,
- source age and market session.

### Validation result

- Evidence State: `SUPPORTED`, `INCONCLUSIVE` or `CHALLENGED`,
- reason codes,
- optional evidence-agreement indicators.

### Policy interface

Policy Actions are configured by the curator or consuming protocol rather than generated by the quant model. Conceptually, each policy is scoped by:

```text
policy owner / consuming application
        +
assetId
        +
referenceId
```

The exact storage layout is an implementation detail, but only the authorized policy owner should be able to create or modify that application's mapping. One application's policy must not automatically apply to another application. Example actions include:

```text
ALLOW
MONITOR
REQUIRE_REVIEW
RESTRICT_NEW_RISK
```

The mapping is configurable. For example, one protocol may map `INCONCLUSIVE` to `MONITOR`, while another may map it to `REQUIRE_REVIEW`. The Risk Guard evaluates the policy; the consuming protocol decides what the returned action does.

### Important interpretation rule

The residual token premium/discount is **not automatically a liquidity premium, mispricing or arbitrage opportunity**.

It is the portion of the tokenized price not explained by the challenger estimate.

---

## 10. Public Interface / Dashboard

The product should remain focused around model validation rather than becoming a generic DeFi dashboard.

### View 1 — Validation Overview

Immediately answer:

1. What is the Observed xStock price?
2. What does the Valtide Model estimate, and what is its Valuation Range?
3. What separately sourced X-Perp evidence is available?
4. Is the evidence fresh and complete?
5. What is the Evidence State?
6. What Policy Action does the configured policy return?

### View 2 — Reference Comparison

Show Observed xStock, Valtide Fair Value and X-Perp separately rather than
hiding disagreement in one composite score.

A compact visual should show where Observed xStock and X-Perp sit relative to
the Valuation Range without implying that the model and its xStock input are
independent market observations.

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

## 11. Original MVP Functional Scope (Historical)

The following requirements preserve the original MVP planning scope. They are
not a current implementation inventory; see Sections 7 and 16 and the linked
product semantics and architecture references for current scope.

### Implemented data capabilities

- ingest the real or reproducible point-in-time inputs needed for one primary asset,
- ingest the selected reference under test and the underlying equity/reference history,
- normalize timestamps and sessions,
- preserve source provenance,
- account for corporate actions / token multipliers where necessary,
- construct a normalized market snapshot for the demo.

### Implemented quantitative capabilities

- implement simple baselines and a quantitative challenger estimator,
- generate defensible calibrated uncertainty and explicit abstention,
- compute reference deviation and Evidence State,
- abstain with `INCONCLUSIVE` when evidence quality or uncertainty is insufficient,
- expose model/version metadata.

### Implemented backend capabilities

- provide normalized market snapshots to the quant layer,
- expose the current valuation / validation result required by the demo,
- support publication of an approved validation attestation to X Layer,
- expose configured Policy Action evaluation separately from the Evidence State.

Exact service boundaries and API shapes are implementation contracts and may evolve as long as the public product semantics remain stable.

### Implemented frontend capabilities

- a focused Validation Overview showing the selected asset, reference under test, evidence, uncertainty and Evidence State,
- the configured Policy Action and X Layer Registry / Risk Guard status,
- the same end-to-end flow demonstrated by the reference consumer.

### Supporting diagnostics

The quant team should still provide enough research evidence to defend the vertical slice:

- simple baseline comparisons,
- point-in-time-correct validation,
- enough historical testing to demonstrate methodology,
- basic model and Evidence State metrics.

Richer historical analytics, expanded backtest dashboards, and additional
external comparators remain possible extensions; the current product already
includes canonical Historical replay, diagnostics, and the unified xStock /
P1a-C / X-Perp evidence path.

### X Layer control path

The deployed product includes an onchain control flow from validation through
policy evaluation and a working reference consumer:

```text
offchain validation
        ↓
onchain validation attestation
        ↓
onchain policy evaluation
        ↓
working consumer flow
```

- `ValtideValidationRegistry.sol` for auditable validation attestations;
- `ValtideRiskGuard.sol` for curator-configured Policy Action evaluation; and
- a minimal `DemoCollateralVault.sol` reference consumer demonstrating composability.

The current testnet deployment and addresses are recorded in
`deployments/xlayer-testnet.json` and `contracts/README.md`.

The contracts are a machine-readable control layer, not a production liquidation oracle or lending protocol.

---

## 12. Non-Goals

The product does not:

- replace Chainlink, Pyth or another production oracle,
- build a lending protocol,
- automatically change LTV / LLTV / caps,
- claim a universal correct LTV,
- execute trades or liquidations,
- claim causal identification of liquidity premium or mispricing,
- become a generic protocol risk dashboard,
- model the entire lending book,
- predict long-horizon stock returns,
- support a large asset universe,
- hide negative benchmark results.

---

## 13. Historical Evaluation

### Required reference baselines

The current product evaluation distinguishes:

1. Observed xStock, the validation target and a P1a-C input;
2. P1a-C Valtide Fair Value and its calibrated Valuation Range;
3. exact-time, separately sourced X-Perp evidence; and
4. a later underlying-market benchmark for offline/ex-post evaluation where
   available.

Other providers or constructed references may appear in historical research
comparisons. They are not additional current Evidence State voters unless a
profile explicitly defines them.

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
- or separately sourced market evidence provides useful disagreement information even when another reference has similar point accuracy,
- Evidence State challenges identify genuinely weak production-reference periods with acceptable false-challenge rates.

### Product success

A risk professional should be able to understand:

- which reference is being validated,
- what separately sourced market evidence says,
- what Valtide says,
- how uncertain Valtide is,
- why the Evidence State is `SUPPORTED`, `INCONCLUSIVE` or `CHALLENGED`,
- what Policy Action the configured policy returns,
- how the methodology performed historically.

---

## 15. Onchain Role

The onchain component is the deployed OKX Dev Day Build a Market control path.
It turns an approved offchain validation result into an auditable Evidence
State and evaluates a Policy Action configured by the curator or consuming
protocol.

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

These are evidence semantics, not policy recommendations. Valtide determines the Evidence State. The policy owner defines the Policy Action mapping. The consumer enforces the resulting action.

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

The Risk Guard evaluates a policy owned by the consuming application. Conceptually, the policy is scoped by:

```text
policy owner / consuming application
        +
assetId
        +
referenceId
```

The exact storage layout is an implementation detail. Only the authorized policy owner should be able to create or modify its mapping, and one application's policy must not automatically apply to another application. The mapping may be:

```text
Evidence State       Example protocol policy
------------------------------------------------
SUPPORTED            ALLOW
INCONCLUSIVE         REQUIRE_REVIEW
CHALLENGED           RESTRICT_NEW_RISK
STALE ATTESTATION    REQUIRE_REVIEW
```

Another protocol may choose `INCONCLUSIVE → MONITOR`. No single mapping is universal.

Valtide publishes the Evidence State, the policy owner defines the mapping, the Risk Guard evaluates it, and the consuming protocol decides how to enforce the returned Policy Action.

### Conceptual consumers

`DemoCollateralVault.sol` is a reference consumer demonstrating that an X Layer application can read the Registry and Risk Guard without embedding Valtide's statistical model. Its demo behavior is:

```text
SUPPORTED
→ new risk allowed

INCONCLUSIVE
→ policy may require review

CHALLENGED
→ policy may restrict new risk
```

The demo consumer is not a production protocol. The current demo restricts new
exposure rather than automatically liquidating existing borrowers.

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

## 16. Current and Future Scope

The current operational scope is NVDAx, SPYx, and AAPLx, each with an
asset-specific model/runtime, canonical historical replay, live scheduler,
and X Layer binding. QQQx remains offline research-only and is not exposed
through the public HTTP API; TSLAx remains research-only.

### Current end-to-end path

- three operational assets: NVDAx, SPYx, and AAPLx;
- Observed xStock as the validation target;
- P1a-C as a model-based challenger that assimilates the current xStock input;
- exact-time X-Perp as separately sourced market evidence;
- real or reproducible point-in-time market inputs;
- a quantitative challenger estimator;
- defensible uncertainty and abstention logic;
- Evidence State generation;
- the operational backend/API path;
- the Validation Console for Operational monitoring, Historical replay, and Demo;
- X Layer `ValtideValidationRegistry.sol`;
- X Layer `ValtideRiskGuard.sol`;
- a minimal `DemoCollateralVault.sol` or equivalent reference consumer;
- deployed X Layer contracts and a working attestation → policy → consumer flow.

### Supporting evidence

- simple baselines;
- point-in-time-correct validation;
- enough historical testing to demonstrate methodology;
- basic model and Evidence State metrics.

Historical validation remains part of the product, while a full research
platform remains outside the current deployed scope.

### Future extensions

- additional assets after their separate evidence and readiness gates pass;
- richer historical replay and backtest UX;
- richer cross-market features and multiple external comparators;
- multiple reference-under-test adapters;
- alerts / webhooks;
- configurable validation thresholds;
- position-level or liquidation-impact simulation;
- protocol-wide portfolio analytics;
- broader asset coverage and complex model families.

---

## 17. Key Risks

### Existing systems may already surface the same information

Kamino Scope, KRAF, Pyth and exchange indices are sophisticated.

**Response:** test incremental information rather than assuming whitespace.

### The challenger model may be weaker than incumbents

Pyth and OKX have stronger data access and production infrastructure.

**Response:** Valtide's differentiation is transparent evidence for
collateral-risk decisions, not a claim that it is always the most accurate
price source.

### Historical data may be too short

Tokenized-equity markets are new.

**Response:** keep the model simple, use walk-forward testing, report sample limitations and prioritize reproducibility.

### Evidence states may be noisy or too often inconclusive

A validation system that challenges everything or abstains from everything is useless.

**Response:** evaluate decision coverage, abstention rate, false challenges, false support and regime-specific performance.

### The product may drift into generic risk analytics

Protocol exposure simulation is attractive but overlaps with mature incumbents.

**Response:** keep the product centered on valuation and model validation.

---

## 18. Positioning

### Public positioning

> **Valtide is a validation layer for tokenized equity collateral. It helps DeFi risk teams assess whether an observed xStock price has enough supporting evidence for a collateral-risk decision.**

### Short pitch

> **Validate the reference. Understand the evidence. Apply your own risk policy onchain.**

### Technical thesis

> **Use a model-based challenger, calibrated uncertainty, and separately sourced X-Perp evidence to produce an auditable Evidence State for curator-owned policy.**

### What Valtide is not

> **Not another 24/7 stock oracle. Not a universal LTV engine. Not another lending protocol. Not an automatic liquidation engine.**

---

## 19. Related Documents

- [`USER_MARKET_RESEARCH.md`](./USER_MARKET_RESEARCH.md)
- [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`METHODOLOGY.md`](./METHODOLOGY.md)
