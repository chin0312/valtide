# Valtide — System Architecture

**Version:** 0.2  
**Last updated:** 20 Sep 2026  
**Status:** Public architecture reference

## 1. Architecture Goal

Valtide is built around one core product primitive:

> **independent validation of tokenized-equity collateral valuation.**

The system must therefore support two related but distinct functions:

1. produce an independent challenger fair-value estimate with uncertainty;
2. compare that estimate and other independent references against a reference under test, preferably a production collateral valuation.

The architecture should remain simple enough for rapid iteration while preserving clean module boundaries between:

- data ingestion,
- normalization,
- quantitative inference,
- reference validation,
- historical replay / backtesting,
- API delivery,
- frontend visualization,
- optional onchain publication.

The quantitative logic remains offchain. The X Layer contract only publishes a compact approved validation snapshot.

---

## 2. Architecture Principles

### 2.1 Contract-first module boundaries

Team components should communicate through stable data shapes rather than vendor-specific responses.

The backend may change data providers without forcing changes to the quant model, and the quant model may evolve without forcing the frontend to understand model internals.

### 2.2 Deployment topology is intentionally flexible

Valtide does **not** require a full microservice deployment for the MVP.

The same logical services can be deployed as:

- a modular monolith,
- separate processes,
- independently deployed microservices later.

For the hackathon, correctness and interface stability are more important than service-discovery or orchestration complexity.

### 2.3 Separate inference from validation

The challenger model should not silently absorb every external reference into one blended price.

The system should preserve the distinction between:

```text
independent challenger estimate
              vs
external evidence / references under test
```

This makes disagreement observable and auditable.

### 2.4 Point-in-time integrity

Historical replay must reconstruct only information that was available at the selected timestamp.

No future market data may leak into historical inference.

### 2.5 Thin onchain layer

The smart contract is an interoperability / publication layer, not a statistical-computation engine and not a production liquidation oracle.

---

## 3. High-Level Architecture

```text
                         DATA SOURCES
       ┌──────────────────────────────────────────────┐
       │                                              │
       │ Tokenized market      Underlying market     │
       │ OKX / xStocks         Equity references     │
       │                                              │
       │ External references / comparators            │
       │ Pyth / Chainlink / OKX X-Perp / others      │
       │                                              │
       └───────────────────┬──────────────────────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ DATA ADAPTERS    │
                  │ source-specific  │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ NORMALIZATION    │
                  │ time / session   │
                  │ units / actions  │
                  │ provenance       │
                  └────────┬─────────┘
                           │
                     Market Snapshot
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
   ┌──────────────────┐        ┌──────────────────┐
   │ CHALLENGER MODEL │        │ REFERENCE SET    │
   │ fair value       │        │ production ref   │
   │ uncertainty      │        │ Pyth / OKX / etc │
   └────────┬─────────┘        └────────┬─────────┘
            │                           │
            └─────────────┬─────────────┘
                          ▼
                 ┌──────────────────┐
                 │ VALIDATION ENGINE│
                 │ deviation        │
                 │ agreement        │
                 │ status / reasons │
                 └────────┬─────────┘
                          │
                    Validation Result
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
   ┌────────────┐  ┌──────────────┐  ┌──────────────────┐
   │ API        │  │ Replay /     │  │ X Layer         │
   │ service    │  │ Backtest     │  │ Validation Feed │
   └─────┬──────┘  └──────────────┘  └────────┬─────────┘
         │                                     │
         └──────────────────┬──────────────────┘
                            ▼
                     ┌──────────────┐
                     │ Next.js Web  │
                     │ validation UI│
                     └──────────────┘
```

---

## 4. Repository Layout

```text
valtide/
├── apps/
│   ├── web/                    # Next.js / TypeScript
│   └── api/                    # FastAPI / Python
│
├── packages/
│   └── quant/                  # Python research + inference package
│       ├── features/
│       ├── models/
│       ├── uncertainty/
│       ├── validation/
│       ├── backtest/
│       └── metrics/
│
├── contracts/
│   ├── src/
│   │   └── ValtideValidationFeed.sol
│   ├── script/
│   └── test/
│
├── data/
│   ├── sample/
│   ├── raw/                    # ignored by Git
│   └── processed/              # ignored by Git
│
├── scripts/
│   ├── fetch_market_data.py
│   ├── build_dataset.py
│   ├── run_backtest.py
│   └── publish_validation.py
│
└── docs/
    ├── USER_MARKET_RESEARCH.md
    ├── PRD.md
    ├── ARCHITECTURE.md
    └── METHODOLOGY.md
```

The internal folder structure may evolve; the architectural boundaries matter more than exact filenames.

---

## 5. Logical Services

### 5.1 Data Adapter Layer

Responsibility:

> Convert source-specific market data into normalized observations.

Potential adapters include:

- OKX OnchainOS,
- xStocks metadata / APIs,
- underlying U.S. equity data,
- Chainlink market data,
- Pyth / Pyth Pro,
- OKX X-Perp reference data where accessible.

Each adapter should preserve:

- source name,
- source timestamp,
- retrieval timestamp where useful,
- instrument identifier,
- price unit,
- market/session metadata,
- quality / status fields if supplied.

Vendor-specific field names should not escape beyond this layer.

### 5.2 Normalization Layer

Responsibilities:

- normalize timestamps to UTC,
- map instruments to canonical asset identifiers,
- normalize price units,
- apply corporate-action / token-multiplier adjustments,
- classify market session,
- calculate source age,
- preserve data provenance,
- align asynchronous observations to a defined snapshot.

Output:

> a canonical **Market Snapshot** suitable for quant inference and validation.

### 5.3 Challenger Model

Responsibility:

> Estimate an independent latent fair value and uncertainty from point-in-time information.

The core model should primarily consume features that preserve independence from the external references later used to validate it.

Outputs include:

- fair value,
- lower / upper interval,
- interval coverage target,
- model-implied move,
- residual token premium / discount,
- model version,
- model diagnostics.

### 5.4 Reference Registry / Evidence Layer

Responsibility:

> Keep external references explicit rather than blending them invisibly into the challenger model.

The **reference under test** is the generic reference that Valtide validates. In the primary product use case, this is a production collateral reference. During the hackathon, when a live production reference is unavailable, it may instead be a reconstructed protocol valuation methodology, a Chainlink reference, an OKX bounded/index reference, or another selected reference used for validation.

Possible reference types:

- production collateral reference,
- reconstructed protocol valuation methodology,
- stale / last trusted underlying,
- Pyth constructed index,
- OKX X-Perp Index or Mark Price,
- Chainlink feed,
- raw tokenized-market price.

Each reference should include:

- source,
- price,
- timestamp,
- age,
- reference type,
- optional market status / confidence metadata.

### 5.5 Validation Engine

Responsibility:

> Compare the reference under test with the challenger estimate and independent evidence.

Outputs include:

- reference-under-test deviation,
- standardized deviation relative to model uncertainty,
- source agreement / disagreement flags,
- validation status,
- reason codes,
- evidence summary.

The validation engine should be deterministic given the challenger output, reference set and configured thresholds.

### 5.6 Replay / Backtest Engine

Responsibility:

> Reconstruct historical states and evaluate both valuation accuracy and validation quality.

It must reuse the same feature-building and validation logic used by the live path.

This prevents a separate research pipeline from silently diverging from production inference.

---

## 6. Data Sources

### 6.1 OKX OnchainOS

Potential uses:

- RWA/token discovery,
- tokenized-market prices,
- historical candles,
- contract metadata,
- current market context.

Relevant documentation:

- [RWA Token List](https://web3.okx.com/onchainos/dev-docs/market/market-rwa-token)
- [Token Advanced Information](https://web3.okx.com/onchainos/dev-docs/market/market-token-advanced-info)
- [Historical Candlesticks](https://web3.okx.com/onchainos/dev-docs/market/market-candlesticks-history)

### 6.2 xStocks

Potential uses:

- canonical token metadata,
- issuer/product metadata,
- token contract addresses,
- corporate-action / multiplier information,
- reference / oracle metadata where exposed.

Reference:

- [xStocks Developer Docs](https://docs.xstocks.fi/developers)

### 6.3 Underlying equity data

The system needs timestamped underlying data sufficient to identify:

- last trusted cash-market reference,
- market session,
- extended/overnight conditions if available,
- subsequent liquid-session benchmark.

The exact provider is an implementation choice constrained by historical coverage, licensing and access.

### 6.4 Chainlink

Potential uses:

- session-aware equity reference data,
- current/live comparison,
- reference-under-test simulation.

Chainlink is a data source / possible reference under test, not Valtide's quantitative moat.

Reference:

- [Chainlink — 24/5 U.S. Equities Streams](https://chain.link/blog/chainlink-24-5-us-equities-streams)

### 6.5 Pyth

Potential uses:

- external constructed benchmark,
- independent evidence source,
- comparison against continuous pricing infrastructure.

For the core challenger-vs-Pyth experiment, Pyth should remain **outside** the challenger feature set.

References:

- [Pyth Indices](https://www.pyth.network/products/pyth-indices)
- [Pyth Pro History API](https://docs.pyth.network/price-feeds/pro/api/history)

### 6.6 OKX X-Perps

Potential uses:

- external derivative reference,
- comparable production methodology,
- validation benchmark during off-hours periods.

OKX describes an Index Price using multiple weighted sources and a ±10% constraint around the last TradFi reference while equity markets are closed.

Reference:

- [OKX — How Stock and Commodity X-Perps Work](https://www.okx.com/en-us/help/how-do-stock-and-commodity-x-perps-work)

---

## 7. Independence Rules

Valtide's product value depends on maintaining a meaningful distinction between the challenger model and the references it validates.

### Core challenger model

For a benchmark experiment against Pyth / OKX:

- do not use Pyth's constructed index as a challenger feature,
- do not use OKX's final X-Perp Index Price as a challenger feature,
- do not train directly on the reference under test in a way that makes the model a trivial replication.

### External evidence layer

After the challenger estimate is generated, the system may compare it with:

- Pyth,
- OKX,
- Chainlink,
- reference under test,
- raw token market,
- other independent evidence.

### Experimental variants

An augmented model may later use external constructed references as features, but it must be labeled separately from the independent challenger model.

---

## 8. Canonical Domain Objects

The exact JSON/API representation may evolve, but the following semantic objects should remain stable.

### 8.1 Market Snapshot

Represents all normalized point-in-time market information available to the inference layer.

Conceptual fields:

```text
asset
observationTimestamp
marketState

underlyingReference
underlyingReferenceTimestamp
referenceAge

tokenPrice
tokenBid / tokenAsk          # optional
tokenVolume                  # optional
tokenLiquidity               # optional

crossMarketFeatures          # optional
sourceProvenance
```

### 8.2 Reference Observation

Represents a named external reference, including the reference under test.

```text
referenceId
source
referenceType
price
timestamp
age
statusMetadata
```

### 8.3 Challenger Estimate

```text
fairValue
lowerBound
upperBound
coverageTarget
modelImpliedMove
residualPremiumDiscount
modelVersion
```

### 8.4 Validation Result

```text
referenceUnderTest
challengerEstimate
externalReferences[]
referenceDeviation
standardizedDeviation
validationStatus
reasonCodes[]
evidenceSummary
```

These semantic boundaries matter more than exact serialization choices.

---

## 9. Historical Data Pipeline

```text
Fetch raw sources
      ↓
Persist raw source snapshots
      ↓
Normalize timestamps / symbols / units
      ↓
Apply corporate-action adjustments
      ↓
Label sessions and source ages
      ↓
Construct point-in-time Market Snapshots
      ↓
Run challenger model
      ↓
Run validation engine
      ↓
Attach later evaluation benchmark
      ↓
Store reproducible backtest results
```

Recommended MVP storage:

- Parquet / CSV for research datasets,
- optional SQLite for replay indexing / metadata,
- raw payloads where legally and technically appropriate for reproducibility.

A production distributed database is not required for the hackathon.

---

## 10. Live Inference Path

```text
Latest source observations
        ↓
Data adapters
        ↓
Normalized Market Snapshot
        ↓
Challenger model
        ↓
Challenger Estimate
        +
Reference Registry
        ↓
Validation Engine
        ↓
Validation Result
        ↓
API / Web / optional X Layer publish
```

The live path and historical replay path should share the same normalization, feature-building and validation code wherever possible.

---

## 11. Backend/API Boundary

The backend is responsible for:

- vendor integrations,
- normalization,
- source caching,
- assembling Market Snapshots,
- calling the quant package,
- exposing Validation Results,
- historical replay,
- backtest result delivery,
- onchain publication workflow.

The backend should **not** reimplement model equations or validation thresholds that belong in the quant package.

Recommended capability groups:

```text
assets / metadata
current validation
historical replay
backtest / evidence
publication status
```

Exact routes are an implementation concern and can be finalized by the engineering team.

---

## 12. Frontend Architecture

The web application should consume normalized public API responses only.

It should not know:

- OKX vendor schemas,
- Pyth raw payload formats,
- Chainlink low-level report formats,
- model implementation details.

Core UI surfaces:

1. **Validation Overview**
2. **Reference Comparison**
3. **Basis / Residual Analysis**
4. **Historical Replay**
5. **Model Evidence / Backtest**
6. **Onchain Publication State**

The UI should preserve disagreement visually instead of collapsing all references into one opaque score.

---

## 13. X Layer Contract

### Purpose

Publish the latest approved validation snapshot in a machine-readable form.

Recommended contract name:

```text
ValtideValidationFeed.sol
```

### Conceptual snapshot

```solidity
struct ValidationSnapshot {
    bytes32 referenceId;
    uint256 referencePriceE8;

    uint256 fairValueE8;
    uint256 lowerBoundE8;
    uint256 upperBoundE8;
    int32 referenceDeviationBps;
    uint8 validationStatus;
    uint64 updatedAt;
    bytes32 modelVersion;
}
```

### Responsibilities

The contract should:

- store the latest snapshot by asset,
- restrict updates to an authorized publisher,
- emit an update event,
- expose read methods,
- expose update timestamp / freshness.

The contract should not:

- fetch external data,
- run statistical inference,
- automatically change another protocol's risk parameters,
- trigger liquidation,
- claim production-oracle guarantees.

---

## 14. Publishing Flow

```text
Validation Result approved by backend
        ↓
schema + sanity checks
        ↓
authorized signer
        ↓
ValtideValidationFeed.sol
        ↓
ValidationUpdated event
        ↓
frontend / external consumer verifies state
```

Private keys must remain server-side and outside source control.

---

## 15. Model and Data Versioning

Every result should identify:

- model version,
- feature/config version where practical,
- source provenance,
- observation timestamp.

Example:

```text
modelVersion = 0.2.0
```

Historical results should not be overwritten as though they were generated by a later model.

Reproducibility matters because Valtide's product is fundamentally a model-validation tool.

---

## 16. Failure Handling

### Missing tokenized-market data

Return an explicit unavailable/degraded state. Do not silently replace the source with an unrelated venue.

### Missing external comparator

The challenger estimate can continue if its required features are available. Validation should mark the missing reference explicitly.

### Stale underlying reference

Retain reference age as an explicit model / UI input.

### Model cannot produce a calibrated interval

Return unavailable or degraded validation rather than fabricated precision.

### Reference-set disagreement

Do not force consensus. Preserve disagreement in the Validation Result.

### Onchain publication failure

Offchain validation remains valid. Publication state should be shown separately.

---

## 17. Security and Integrity

- Keep API secrets backend-only.
- Preserve source timestamps and provenance.
- Prevent look-ahead leakage in historical replay.
- Schema-validate model output before public delivery or publication.
- Isolate the contract publisher wallet from user funds.
- Clearly distinguish market source time from retrieval time.
- Label Valtide as an independent reference / validation system, not a guaranteed liquidation oracle.

---

## 18. Deployment Strategy

The architecture supports both a modular monolith and later service separation.

### Hackathon-friendly deployment

```text
Next.js web
      ↓
FastAPI backend
      ↓
Python quant package

FastAPI backend
      ↓
X Layer RPC
      ↓
ValtideValidationFeed.sol
```

This is sufficient if module contracts remain clean.

### Future service separation

If scale or ownership requires it, the following can be independently deployed later:

- data ingestion service,
- quant inference service,
- replay / research service,
- publisher service.

No product value depends on using microservices in the MVP.

---

## 19. Architecture Principle

> **Keep the challenger independent, keep disagreement visible, keep historical replay point-in-time correct, and keep the onchain layer thin.**

The architecture exists to make Valtide's validation claim auditable—not to maximize engineering complexity.
