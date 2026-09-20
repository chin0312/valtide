# Valtide

> **Independent oracle and model validation for tokenized-equity collateral.**

> **A second opinion for tokenized-equity collateral valuation.**

Valtide is being built for **OKX Dev Day 2026**. It is an independent oracle/model-validation layer for tokenized-equity collateral—not a production-ready oracle.

## The problem

Tokenized equities can trade when the strongest traditional equity reference is unavailable or degraded. For DeFi lending markets, this creates a difficult collateral-valuation problem:

- the last trusted underlying price may be stale;
- the tokenized market may contain genuine new price discovery;
- tokenized prices may also contain venue-specific premiums, discounts, or dislocations; and
- collateral valuation can directly affect borrowing capacity and liquidation decisions.

This is not an empty market. Chainlink provides sophisticated equity pricing infrastructure, Pyth provides constructed 24/7 equity references, and protocols such as Kamino already operate sophisticated risk systems. Curators and protocols also make their own collateral-risk decisions.

Valtide focuses on a narrower wedge: independent validation of the valuation a protocol is relying on.

## The Valtide thesis

Valtide is an **independent oracle/model-validation layer for tokenized-equity collateral**.

The central user is the **DeFi curator / lending-protocol risk team**. The core question is:

> **Is the collateral valuation the protocol is relying on supported by independent market evidence?**

Valtide builds an independent challenger view from tokenized-market and related market information, then makes disagreement visible:

```text
Production collateral reference
              │
              ▼
       Valtide validation
       ┌──────┼──────┐
       │      │      │
 challenger  token   external
 estimate   market   references
       │      │      │
       └──────┼──────┘
              ▼
    SUPPORT / WATCH / REVIEW
```

Core outputs are intended to include:

- challenger fair-value estimate;
- calibrated uncertainty interval;
- observed token/reference basis;
- model-implied move;
- residual token premium/discount;
- reference-validation status; and
- historical validation evidence.

The challenger fair-value estimator is a component of the validation system, not the entire product positioning.

## What Valtide is not

Valtide is not:

- another generic raw-price oracle;
- a replacement for Chainlink or Pyth;
- another lending protocol;
- an automatic LTV controller;
- a liquidation engine;
- a trading or arbitrage bot;
- a universal source of the “correct” collateral LTV; or
- a production-certified oracle.

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

See [`Valuation Methodology`](./docs/METHODOLOGY.md) for the research design, uncertainty, validation, and evaluation details.

## Intended hackathon MVP

Primary research / validation asset:

```text
NVDAx / NVDA
```

Secondary validation asset, if P0 succeeds:

```text
SPYx / SPY
```

The intended MVP flow is:

```text
point-in-time market data
        ↓
normalization
        ↓
challenger valuation model
        ↓
uncertainty + basis analysis
        ↓
reference validation
        ↓
historical replay / backtest
        ↓
API + focused web interface
        ↓
optional X Layer reference publication
```

These are intended hackathon capabilities, not claims that they are already implemented.

## Architecture overview

```text
Market / Reference Data
          │
          ▼
   Data Normalization
          │
          ▼
      Quant Engine
   ┌──────┼───────┐
   │      │       │
Fair Value│   Uncertainty
          │
   Basis / Validation
          │
          ▼
       Backend API
       │           │
       ▼           ▼
 Web Interface   X Layer
                 Reference Feed
```

Quantitative and statistical computation stays offchain. The backend provides normalized data and API access, the web app is the curator-facing interface, and an optional X Layer contract can publish compact machine-readable reference snapshots. The contract does not perform the statistical model itself.

The architecture has clear modular/service boundaries, with deployment topology intentionally flexible during the hackathon. It does not require a microservices decision at this stage.

## Repository structure

```text
apps/api/          backend and data services
apps/web/          frontend application
packages/quant/    quantitative models and backtesting
contracts/         X Layer smart contracts
data/sample/       small reproducible public samples
data/raw/          local raw datasets, gitignored
data/processed/    local processed datasets, gitignored
scripts/           utility / data / deployment scripts
docs/              canonical project documentation
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

- [`User & Market Research`](./docs/USER_MARKET_RESEARCH.md) — market context, users, existing infrastructure, and the product wedge.
- [`Product Requirements`](./docs/PRD.md) — user workflows, scope, requirements, non-goals, and success criteria.
- [`System Architecture`](./docs/ARCHITECTURE.md) — logical boundaries, data flow, deployment flexibility, and the optional onchain publication layer.
- [`Valuation Methodology`](./docs/METHODOLOGY.md) — challenger valuation, uncertainty, validation, baselines, and historical evaluation.

## Project status

> Valtide is under active development for OKX Dev Day 2026. The repository currently contains the project specification and implementation scaffold; components will land incrementally during the hackathon.

| Area                    | Status       |
| ----------------------- | ------------ |
| Research / positioning  | defined      |
| Product specification   | defined      |
| Architecture            | drafted      |
| Methodology             | drafted      |
| Implementation          | in progress  |
| Quant validation        | pending      |
| X Layer deployment      | pending      |

## Development

Component-specific development instructions will be added as implementation lands. There is currently no frontend, backend, or quant package setup to install.

## Disclaimer

> Valtide is a hackathon research prototype. It is not a production oracle, lending system, financial product, or financial advice.
