# Valtide — System Architecture

**Version:** 0.3  
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
- onchain validation attestation,
- curator-configured policy evaluation,
- reference-consumer integration.

The quantitative logic remains offchain. X Layer provides a strong protocol interface for attestations, policy evaluation and consumer integration without moving statistical computation onchain.

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

### 2.5 Thin computation, strong protocol interface

The X Layer contracts are an interoperability and control layer, not a statistical-computation engine, universal LTV engine or production liquidation oracle. The Registry proves that an authorized publisher committed a result at a time; the Risk Guard applies a curator-selected policy to that evidence.

---

## 3. High-Level Architecture

```text
OFFCHAIN VALIDATION PLANE

Market / Reference Data
          │
          ▼
   Data Adapters
          │
          ▼
   Normalization
          │
          ▼
     Quant Engine
          │
          ▼
  Validation Engine
          │
          ├──────────────► API / Dashboard
          │
          ▼
 Evidence State + Attestation
          │
          ▼
X LAYER CONTROL PLANE

ValtideValidationRegistry
          │
          ▼
   ValtideRiskGuard
          │
          ▼
Protocol / Vault / Agent Consumer

Historical replay and backtesting remain offchain and share the same
normalization, feature-building and validation semantics.
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
│   ├── src/                    # intended X Layer control contracts
│   │   ├── ValtideValidationRegistry.sol
│   │   ├── ValtideRiskGuard.sol
│   │   └── DemoCollateralVault.sol
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
- Evidence State: `SUPPORTED`, `INCONCLUSIVE` or `CHALLENGED`,
- reason codes,
- evidence summary.

The validation engine should be deterministic given the challenger output, reference set and configured thresholds.

### 5.6 Replay / Backtest Engine

Responsibility:

> Reconstruct historical states and evaluate both valuation accuracy and validation quality.

It must reuse the same feature-building and validation logic used by the live path.

This prevents a separate research pipeline from silently diverging from production inference.

### 5.7 X Layer Control Plane

The X Layer control plane consumes an approved offchain validation result. It does not reproduce the statistical model.

It consists conceptually of:

- **ValtideValidationRegistry.sol** — stores and exposes auditable validation attestations per asset/reference pair;
- **ValtideRiskGuard.sol** — maps Evidence State to a Policy Action selected by the curator or consuming protocol; and
- **DemoCollateralVault.sol** — a reference consumer proving that another X Layer application can consume the control result.

The Registry should commit:

- the reference identity and price,
- challenger fair value and calibrated bounds,
- Evidence State,
- evidence/model provenance,
- observation, publication and expiry timestamps.

The Risk Guard should expose the result of a configurable policy. Valtide determines the Evidence State; the consuming protocol determines what `ALLOW`, `MONITOR`, `REQUIRE_REVIEW` or `RESTRICT_NEW_RISK` means for its own operations.

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

### 6.5 X Layer ecosystem context

OKX describes Chainlink Data Streams as available on X Layer mainnet for high-speed market data, including 24/5 equities and tokenized-treasury pricing. The same ecosystem context identifies RWA collateral valuation and automated risk-management applications as relevant uses.

Valtide complements this infrastructure. A Chainlink equity Data Stream on X Layer may serve as the reference under test, external comparison evidence, or a live integration where technically accessible, but it must remain outside the independent challenger feature set when it is the benchmark being evaluated.

Reference:

- [OKX — Chainlink Data Streams on X Layer](https://web3.okx.com/learn/xlayer-chainlink-data-streams)

### 6.6 Pyth

Potential uses:

- external constructed benchmark,
- independent evidence source,
- comparison against continuous pricing infrastructure.

For the core challenger-vs-Pyth experiment, Pyth should remain **outside** the challenger feature set.

References:

- [Pyth Indices](https://www.pyth.network/blog/24-7-finance-needs-24-7-price-infrastructure-introducing-pyth-indices)
- [Pyth Pro History API](https://docs.pyth.network/price-feeds/pro/api/history)

### 6.7 OKX X-Perps

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
evidenceState
evidenceHash
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
Evidence State + Validation Attestation
        ↓
API / Web
        ↓
X Layer Validation Registry
        ↓
X Layer Risk Guard
        ↓
Reference Consumer
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
- onchain attestation workflow,
- Risk Guard policy evaluation.

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
6. **Evidence State / Policy Action**
7. **X Layer Registry / Risk Guard State**

The UI should preserve disagreement visually instead of collapsing all references into one opaque score.

---

## 13. X Layer Control Plane

The X Layer contracts are a required part of the intended OKX Dev Day Build a Market MVP. They expose auditable validation evidence and configurable policy controls to other X Layer applications without embedding Valtide's statistical model in those applications.

The principle is:

> **Thin computation, strong protocol interface.**

### 13.1 ValtideValidationRegistry.sol

Purpose:

> **Store and expose auditable Valtide validation attestations on X Layer.**

Conceptual state:

```solidity
enum EvidenceState {
    SUPPORTED,
    INCONCLUSIVE,
    CHALLENGED
}

struct ValidationAttestation {
    bytes32 referenceId;
    uint256 referencePriceE8;

    uint256 fairValueE8;
    uint256 lowerBoundE8;
    uint256 upperBoundE8;

    int32 referenceDeviationBps;
    EvidenceState evidenceState;

    bytes32 evidenceHash;
    bytes32 modelVersion;

    uint64 observedAt;
    uint64 publishedAt;
    uint64 validUntil;
}
```

The asset may remain the mapping key, so it does not need to be duplicated inside the struct.

`evidenceHash` commits the attestation to the corresponding offchain evidence, normalized observation and model result. It provides provenance and auditability; it does not make the offchain data objectively correct.

`observedAt` is the market timestamp to which the validation refers. `publishedAt` is when the attestation was committed to X Layer. `validUntil` allows consumers to reject stale validations.

The Registry should conceptually:

- store the latest attestation per asset/reference pair,
- restrict publishing to an authorized Valtide publisher,
- emit an update event,
- expose read methods,
- expose freshness and provenance fields.

### 13.2 ValtideRiskGuard.sol

Purpose:

> **Translate Valtide Evidence States into a Policy Action defined by the consuming curator or protocol.**

Conceptual state:

```solidity
enum PolicyAction {
    ALLOW,
    MONITOR,
    REQUIRE_REVIEW,
    RESTRICT_NEW_RISK
}

struct ValidationPolicy {
    uint64 maxAge;

    PolicyAction onSupported;
    PolicyAction onInconclusive;
    PolicyAction onChallenged;
    PolicyAction onStale;
}
```

A conceptual evaluation interface may resemble:

```solidity
function evaluate(
    bytes32 assetId,
    bytes32 referenceId
)
    external
    view
    returns (
        EvidenceState evidenceState,
        PolicyAction policyAction,
        bool fresh
    );
```

The exact implementation does not need to be frozen in the documentation. The important boundary is:

```text
Valtide evidence
        ≠
protocol policy
```

The Risk Guard exposes the result of the policy. The consumer protocol decides how that result affects its own operations.

### 13.3 DemoCollateralVault.sol

The MVP should include a minimal reference consumer demonstrating composability. `DemoCollateralVault.sol` is not a full lending protocol and is not production infrastructure.

Example behavior:

```text
SUPPORTED
→ new risk allowed

INCONCLUSIVE
→ policy may require review

CHALLENGED
→ policy may restrict new risk
```

For the demo, prefer restricting **new exposure** rather than automatically liquidating existing borrowers.

### 13.4 Control-plane boundaries

Offchain:

- market-data normalization,
- feature engineering,
- challenger estimation,
- uncertainty calibration,
- Evidence State generation,
- historical backtesting.

On X Layer:

- validation attestation,
- provenance commitment,
- timestamps and freshness,
- Evidence State availability,
- curator-configured Policy Action,
- consumer-facing risk controls.

The contracts must not:

- calculate the model onchain,
- control user funds,
- set universal LTVs,
- liquidate positions,
- claim production-oracle guarantees.

---

## 14. Publishing Flow

```text
Evidence State / Validation Attestation approved by backend
        ↓
schema + sanity checks
        ↓
authorized signer
        ↓
ValtideValidationRegistry.sol
        ↓
ValidationUpdated event
        ↓
ValtideRiskGuard.sol
        ↓
DemoCollateralVault.sol / external consumer evaluates policy
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

### Onchain attestation or policy-evaluation failure

Offchain validation remains valid, but consumers should treat missing or stale attestations and unavailable policy evaluation as explicit degraded states.

---

## 17. Security and Integrity

- Keep API secrets backend-only.
- Preserve source timestamps and provenance.
- Prevent look-ahead leakage in historical replay.
- Schema-validate model output before public delivery or publication.
- Isolate the contract publisher wallet from user funds.
- Clearly distinguish market source time from retrieval time.
- Treat the Registry as provenance and availability infrastructure, not proof that the statistical model is correct.
- Treat the Risk Guard as a policy interface, not a universal financial-policy engine.
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
ValtideValidationRegistry.sol
      ↓
ValtideRiskGuard.sol
      ↓
DemoCollateralVault.sol / protocol consumer
```

This is sufficient if module contracts remain clean.

### Future service separation

If scale or ownership requires it, the following can be independently deployed later:

- data ingestion service,
- quant inference service,
- replay / research service,
- attestation / policy service.

No product value depends on using microservices in the MVP.

---

## 19. Architecture Principle

> **Keep the challenger independent, keep disagreement visible, keep historical replay point-in-time correct, and keep the protocol interface strong without moving statistical computation onchain.**

The architecture exists to make Valtide's validation claim auditable—not to maximize engineering complexity.
