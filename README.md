# Valtide

> **Independent collateral-valuation control for tokenized equities on X Layer.**

Valtide helps DeFi curators and RWA risk teams determine whether a collateral valuation is supported, inconclusive or materially challenged by independent market evidence — and makes that validation usable by configurable risk policies on X Layer.

Valtide is being built for **OKX Dev Day 2026 — Build a Market**. It is not a production oracle, lending protocol or automatic liquidation engine.

## The problem

Tokenized equities can trade when the strongest traditional equity reference is unavailable or degraded. For DeFi lending markets, this creates a difficult collateral-valuation problem:

- the last trusted underlying price may be stale;
- the tokenized market may contain genuine new price discovery;
- tokenized prices may also contain venue-specific premiums, discounts, or dislocations; and
- collateral valuation can directly affect borrowing capacity and liquidation decisions.

This is not an empty market. Chainlink provides sophisticated equity pricing infrastructure, Pyth provides constructed 24/7 equity references, OKX X-Perps already perform multi-source off-hours price construction and controls, and protocols such as Kamino already operate sophisticated risk systems. Curators and protocols also make their own collateral-risk decisions.

Valtide focuses on the narrower control-layer question: is the reference a protocol is relying on still supported by independent evidence, and what should a curator-configured policy do with that evidence?

## The Valtide thesis

Valtide is an **independent collateral-valuation control layer for tokenized equities on X Layer**.

The primary user is the **DeFi curator / lending-protocol risk team / RWA risk manager**. The core question is:

> **Is the collateral valuation the protocol is relying on supported by independent market evidence?**

The quantitative challenger fair-value model remains a component of the validation system, not the entire product positioning. Valtide makes the evidence state auditable and usable by a policy configured by the curator or consuming protocol.

## Jobs to be done

> **When I manage a lending market using tokenized equities as collateral and my reference price becomes stale, uncertain or disagrees with other markets, help me independently determine whether that valuation is still supported by market evidence, so I can decide whether to continue normal operations, investigate the discrepancy or restrict additional risk exposure — and have the consuming application apply that policy consistently onchain.**

The product loop is:

```text
VALIDATE → DIAGNOSE → TRIAGE → GUARD
```

- **VALIDATE** — Is the reference I rely on still supported?
- **DIAGNOSE** — Why are the reference, tokenized market and independent evidence disagreeing?
- **TRIAGE** — Is the evidence strong enough to support the reference, challenge it, or is the result inconclusive?
- **GUARD** — How should my own predefined risk policy respond to that evidence?

Valtide performs the first three jobs directly. For the fourth, it provides standardized onchain evidence and policy infrastructure while the curator or protocol defines the actual policy. The consumer enforces the resulting action.

> **Valtide determines the evidence state. The curator or protocol determines the policy action. The consumer enforces the resulting action.**

## Evidence state and policy action

Valtide reports an **Evidence State**, not a financial-policy recommendation:

- **SUPPORTED** — available independent evidence does not provide a material reason to challenge the reference under test. This does not prove the reference is correct.
- **INCONCLUSIVE** — evidence is not sufficiently strong or consistent to support or materially challenge the reference. High uncertainty, poor token-market quality, unavailable comparators, stale data, disagreement, or a decision boundary can all lead to abstention.
- **CHALLENGED** — the reference under test is materially inconsistent with sufficiently strong independent evidence. This does not prove the reference is definitely wrong.

A separate **Policy Action** is configured by the consuming curator or protocol. Example actions include:

```text
ALLOW              normal new exposure permitted
MONITOR            continue with additional observation
REQUIRE_REVIEW     require a human or protocol review
RESTRICT_NEW_RISK  reject or limit additional exposure
```

The mapping is configurable and owned by the consuming application for its asset/reference pair. One protocol may map `INCONCLUSIVE` to `MONITOR`; another may map it to `REQUIRE_REVIEW`. Valtide does not prescribe one universal mapping.

## What Valtide is not

Valtide is not:

- another generic raw-price oracle or a replacement for Chainlink or Pyth;
- another lending protocol, automatic LTV controller or liquidation engine;
- a trading or arbitrage bot;
- a universal source of the “correct” collateral LTV; or
- a production-certified oracle.

## From evidence to action

```text
Reference Under Test
        +
Tokenized Market
        +
Independent Market Evidence
        ↓
Valtide Challenger Model
        ↓
Fair Value + Calibrated Uncertainty
        ↓
Validation Engine
        ↓
Evidence State
SUPPORTED / INCONCLUSIVE / CHALLENGED
        ↓
X Layer Validation Registry
        ↓
Curator-Defined Policy
        ↓
Valtide Risk Guard
        ↓
Protocol / Vault / Agent Consumer
```

This is one validation system with two interfaces:

```text
Human interface   → dashboard / historical evidence
Machine interface → X Layer Registry + Risk Guard
```

The Registry exposes the Evidence State, the Risk Guard evaluates the configured Policy Action, and the consumer contract performs the actual enforcement. Valtide does not directly control another protocol.

## Quantitative hypothesis

Valtide tests whether tokenized-market price discovery and related point-in-time information can provide useful **independent evidence** beyond simple alternatives.

The intended benchmark set is:

```text
last trusted underlying reference
raw tokenized-market price
simple statistical baselines
external constructed references where accessible
Valtide challenger model
```

This is a falsifiable research hypothesis, not a performance claim. If existing references dominate and Valtide provides no incremental validation information, the thesis should be reconsidered.

See [`Valuation Methodology`](./docs/METHODOLOGY.md) for the research design, uncertainty, evidence states, abstention, and evaluation details.

## Intended hackathon MVP

Primary research / validation asset:

```text
NVDAx / NVDA (subject to actual data access)
```

Secondary validation asset, P1 / stretch:

```text
SPYx / SPY
```

The intended Build a Market MVP is:

```text
point-in-time market data
        ↓
normalization
        ↓
challenger valuation model
        ↓
uncertainty + evidence analysis
        ↓
offchain validation
        ↓
X Layer validation attestation
        ↓
onchain policy evaluation
        ↓
working reference consumer
```

X Layer is a required part of the intended MVP architecture, but these capabilities are not claims that implementation or deployment already exists.

### Submission-critical P0

The submission-critical slice is one complete, defensible vertical path:

```text
NVDAx / NVDA (or the best-supported fallback)
        ↓
one reference under test
        ↓
point-in-time market inputs
        ↓
simple challenger + uncertainty / abstention
        ↓
Evidence State
        ↓
Validation Registry → Risk Guard → reference consumer
        ↓
focused dashboard showing the same flow
```

Supporting P0 evidence includes simple baselines, point-in-time correctness, enough historical testing to demonstrate defensibility, and basic model / Evidence State metrics.

### P1 / stretch

Second assets such as SPYx, richer replay and backtest UX, additional comparators, configurable adapters, alerts, position-impact simulation and broader asset coverage should not block the vertical slice.

> **One complete, defensible vertical slice is more important than several partially implemented features.**

## Architecture overview

```text
Market / Reference Data
          │
          ▼
   Data Normalization
          │
          ▼
      Quant Engine
          │
          ▼
  Validation Engine
          │
          ▼
X Layer Validation Registry
          │
          ▼
     Risk Guard
          │
          ▼
 Protocol / Vault / Agent

Human interface   → dashboard / historical evidence
Machine interface → Registry + Risk Guard
```

The principle is **thin computation, strong protocol interface**.

Offchain work includes market-data normalization, feature engineering, challenger estimation, uncertainty calibration, evidence-state generation, and historical backtesting. X Layer provides validation attestations, provenance commitments, timestamps and freshness, evidence-state availability, curator-configured policy evaluation, and consumer-facing risk controls. Statistical computation does not move onchain.

X Layer's existing RWA and market-data infrastructure provides the ecosystem context for this design. OKX has described Chainlink Data Streams as available on X Layer mainnet for high-speed market data, including equities and RWA collateral-management use cases; Valtide complements that infrastructure with an independent validation and control layer rather than replacing it. See the [OKX Chainlink Data Streams announcement](https://web3.okx.com/learn/xlayer-chainlink-data-streams).

## Repository structure

```text
apps/api/                   backend and data services
apps/web/                   frontend application
valtide-quant-service-p1ac/ packaged quantitative runtime and artifacts
contracts/                  X Layer control-layer smart contracts
deployments/                public deployment manifests
data/                       ignored generated/runtime diagnostics
scripts/                    utility / data / deployment scripts
docs/                       canonical project documentation
```

## Team

| Member   | GitHub                                           | Role            |
| -------- | ------------------------------------------------ | --------------- |
| Kai Ze   | [@chin0312](https://github.com/chin0312)         | Product Manager |
| Xin Tong | [@landonzhao](https://github.com/landonzhao)     | Backend         |
| James    | [@Orange-eat97](https://github.com/Orange-eat97) | Quant           |
| Valerie  | [@valeriexylim](https://github.com/valeriexylim) | Frontend        |

At a high level:

- **Kai Ze / `chin0312`** — product direction, requirements, integration and hackathon delivery
- **Xin Tong / `landonzhao`** — backend, market-data ingestion and normalized data interfaces
- **James / `Orange-eat97`** — quantitative methodology, models, uncertainty and backtesting
- **Valerie / `valeriexylim`** — frontend and curator-facing product experience

## Documentation

These four files are the canonical project references:

- [`User & Market Research`](./docs/USER_MARKET_RESEARCH.md) — market context, users, competitive infrastructure, JTBD, and the X Layer ecosystem fit.
- [`Product Requirements`](./docs/PRD.md) — jobs, evidence states, policy separation, workflows, scope, and demo requirements.
- [`System Architecture`](./docs/ARCHITECTURE.md) — offchain validation plane, X Layer control plane, trust boundaries, and deployment flexibility.
- [`Valuation Methodology`](./docs/METHODOLOGY.md) — challenger valuation, uncertainty, evidence states, abstention, baselines, and historical evaluation.

## Project status

> Valtide is under active development for OKX Dev Day 2026. The repository
> contains the backend/quant vertical slice, a deployed X Layer testnet
> control plane, and a credentialed testnet publisher smoke result. Backend
> deployment and frontend integration remain in progress; production readiness
> remains out of scope.

| Area                    | Status       |
| ----------------------- | ------------ |
| Research / positioning  | defined      |
| Product specification   | defined      |
| Architecture            | drafted      |
| Methodology             | drafted      |
| Implementation          | backend/quant vertical slice implemented; deployment/frontend integration in progress |
| Quant validation        | P1a-C runtime integrated |
| X Layer deployment      | testnet control plane deployed |
| Reference consumer      | DemoCollateralVault deployed |
| Backend publisher       | wired; credentialed X Layer testnet write smoke passed |

## Development

Component-specific setup instructions live in `apps/api/README.md` and the
packaged quant service README. Backend publication is testnet-only, disabled by
default, and does not imply an audit or production deployment.

## Disclaimer

> Valtide is a hackathon research prototype. It is not a production oracle, lending system, financial product, or financial advice.
