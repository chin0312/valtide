# Valtide — User & Market Research

**Version:** 1.3  
**Status:** Public reference

## 1. Executive Summary

Tokenized equities are moving from a trading product toward a programmable collateral primitive, but the market is still early.

As of September 2026, xStocks reports more than **$800M in assets under management**, **700+ tokenized stocks and ETFs**, and **$40B+ in transaction volume**. Tokenized equities are also entering live lending workflows: Ondo has brought SPYon and QQQon into Morpho markets, while Kraken has launched xStocks Vaults for SPYx, QQQx and NVDAx using onchain lending infrastructure including Kamino.

This creates a real risk-management problem. Tokenized equities can remain transferable and trade outside the strongest traditional cash-market session. A lending protocol may therefore need to value collateral when:

- the underlying exchange is closed,
- traditional references are stale or session-limited,
- tokenized venues continue trading,
- multiple constructed or derivative references disagree,
- liquidation decisions remain economically consequential.

However, research shows that this is **not an empty infrastructure gap**.

Existing systems already solve substantial parts of the problem:

- **Chainlink** provides low-latency U.S. equity market data and tokenized-equity feeds with session and market-status context.
- **Pyth** has launched proprietary 24/7 constructed indices for U.S. equities and other traditional assets.
- **OKX X-Perps** construct a proprietary stock/ETF Index Price from multiple sources and bound the live index around the last TradFi reference when equity markets are closed.
- **Kamino Scope** is already an oracle aggregator with validation logic, reference-price tolerance, TWAP support and integrations for multiple oracle types; Kamino separately maintains protocol-side risk analytics.
- **Morpho** gives market creators and curators control over the oracle and lending-risk configuration rather than prescribing one universal valuation method.

The implication is important:

> **Valtide should not compete as “another 24/7 stock-price oracle.”**

A more defensible role is an **independent collateral-valuation control layer for tokenized equities on X Layer**.

Valtide uses an independent challenger model to estimate fair value and uncertainty, but the product-level question is broader:

> **“Is the collateral valuation a protocol is relying on supported by independent market evidence?”**

The fair-value estimator is therefore a tool inside the product, not the entire value proposition.

Valtide's current hypothesis is deliberately falsifiable. If its independent model and cross-reference validation do not add useful information beyond existing production references, Pyth, tokenized-market prices and simple controls, the thesis should be reconsidered.

---

## 2. Market Context

### 2.1 Tokenized equities are early, but no longer hypothetical

Tokenized stocks and ETFs remain small relative to global public-equity markets, but their infrastructure and product coverage are expanding quickly.

Recent production milestones include:

- xStocks expanding to hundreds of tokenized equities and ETFs;
- tokenized stocks trading continuously on crypto-native venues;
- tokenized securities being accepted as collateral in onchain lending markets;
- exchange-distributed vault products making tokenized-equity lending accessible through familiar interfaces;
- continuous equity-index products being launched specifically for 24/7 digital-asset markets.

This is best understood as an **emerging infrastructure market**, not a mature software category with thousands of established buyers.

Sources:

- [xStocks](https://xstocks.com/)
- [Kamino — xStocks Vaults Launch on Kraken](https://kamino.com/blog/xstocks-vaults-launch-on-kraken-powered-by-kamino)
- [Morpho — How Tokenized Stocks Fit Into Onchain Credit](https://morpho.org/blog/how-tokenized-stocks-fit-into-onchain-credit)

### 2.2 Tokenized equities create asynchronous market structure

Traditional U.S. cash-equity markets do not provide the same quality of price discovery at every hour of the week. Tokenized representations, derivatives and crypto-native markets can continue trading when the strongest underlying cash session is unavailable.

A simplified structure is:

```text
Traditional underlying / primary reference
              │
        strongest session ends
              │
              ▼
Tokenized equities + derivatives + other references
              │
      continue discovering price
              │
              ▼
Protocol still needs collateral valuation
```

During these periods, a token/reference basis may reflect several things at once:

- genuine new information,
- different venue liquidity,
- hedging constraints,
- temporary dislocation,
- model differences,
- stale traditional references.

Therefore:

> **A tokenized-equity price differing from the last cash-market reference is neither automatically wrong nor automatically a risk-free arbitrage.**

The hard question is how much weight a risk system should place on each available signal.

---

## 3. Why Collateral Valuation Matters

In an overcollateralized lending market, collateral value directly affects:

- borrowing capacity,
- borrower health,
- liquidation eligibility,
- liquidation economics,
- potential bad debt.

A price that is too high may allow excessive borrowing or delay necessary liquidation. A price that is too low may trigger unnecessary liquidation or make the market unnecessarily capital-inefficient.

For tokenized equities, off-hours pricing introduces an additional policy trade-off:

```text
Use a conservative/stale anchor
        ↓
reduce false-liquidation risk
but accept more gap / delayed-liquidation risk

vs.

Use a continuously constructed price
        ↓
react faster to new information
but accept more model / synthetic-price risk
```

This is not merely a technical feed-selection problem. It is a **model-risk and risk-policy problem**.

A protocol can rationally prefer a more conservative valuation even when a newer constructed price exists, because liquidation is irreversible.

---

## 4. Primary User

### DeFi curator / lending-protocol risk team

Valtide's primary user is the party responsible for deciding whether the protocol's collateral assumptions remain defensible.

Representative users include:

- lending-market curators,
- protocol risk councils,
- vault managers,
- RWA credit teams,
- independent risk-service providers.

Their core job is not simply:

> “Give me another price.”

It is closer to:

> **“Give me independent evidence that supports or challenges the collateral valuation and risk assumptions I am relying on.”**

Relevant decisions may include:

- reviewing an oracle or valuation methodology,
- investigating a divergence event,
- keeping or changing exposure limits,
- changing vault allocation,
- tightening or loosening risk parameters,
- creating a differently configured market,
- deciding whether an apparent off-hours move deserves action.

Valtide does not need to make those downstream policy decisions automatically.

### Primary job to be done

> **When I manage a lending market using tokenized equities as collateral and my reference price becomes stale, uncertain or disagrees with other markets, help me independently determine whether that valuation is still supported by market evidence, so I can decide whether to continue normal operations, investigate the discrepancy or restrict additional risk exposure — and have the consuming application apply that policy consistently onchain.**

The job has four connected parts:

```text
VALIDATE
Is the reference I rely on still supported?

DIAGNOSE
Why are the reference, tokenized market and independent evidence disagreeing?

TRIAGE
Is the evidence strong enough to support the reference, challenge it, or is the result inconclusive?

ACT / GUARD
How should my own predefined risk policy respond to that evidence?
```

Valtide performs validation, diagnosis and triage. The curator or consuming protocol owns the Policy Action, and the consumer enforces the resulting action. This separates independent evidence from downstream decisions such as `ALLOW`, `MONITOR`, `REQUIRE_REVIEW` or `RESTRICT_NEW_RISK`.

---

## 5. Existing Market Infrastructure

### 5.1 Chainlink: production market-data and oracle infrastructure

Chainlink already provides sophisticated equity-market data rather than a single simplistic last-trade feed. Its U.S. equity products include low-latency pricing and market/session context, and Chainlink has launched tokenized-equity data feeds for DeFi use cases.

This means the following are **not** credible standalone Valtide differentiators:

- session awareness,
- basic staleness checks,
- simple bid/ask context,
- “bringing equity prices onchain.”

Sources:

- [Chainlink — 24/5 U.S. Equities Streams](https://chain.link/blog/chainlink-24-5-us-equities-streams)
- [Chainlink — Tokenized Equity Feeds](https://dev.chain.link/changelog/tokenized-equity-feeds-launch-with-ondo-finance)

### 5.2 Pyth: direct competition to the original fair-value thesis

Pyth launched proprietary **24/7 constructed indices** for traditional assets whose underlying markets do not trade continuously. Its June 2026 launch materials explicitly included U.S. single-name equities such as NVDA, TSLA, AAPL, MSFT and GOOGL, and Pyth has continued expanding the index suite.

Pyth explicitly frames these products as constructed references that can continue pricing through nights and weekends.

That substantially weakens the thesis:

> “The market is missing a 24/7 fair-value model for equities.”

Pyth has institutional data contributors, production infrastructure, continuous delivery and commercial distribution that a hackathon prototype cannot replicate.

Valtide therefore should treat Pyth as:

1. a strong incumbent / benchmark,
2. a potential independent evidence source,
3. proof that continuous fair-value construction is already an established product direction.

Public product availability and historical-access terms can vary by index and should be verified at implementation time.

Sources:

- [Pyth — Introducing 24/7 Indices](https://www.pyth.network/blog/24-7-finance-needs-24-7-price-infrastructure-introducing-pyth-indices)
- [Pyth Indices](https://www.pyth.network/products/pyth-indices)
- [Pyth — 24/7 Indices Expansion](https://www.pyth.network/blog/pyth-24-7-indices-expansion-amazon-meta-samsung-and-more)

### 5.3 OKX X-Perps: hybrid off-hours price construction plus controls

OKX's stock and ETF X-Perps provide another important comparison because their pricing methodology already combines several of the signal families Valtide originally considered.

OKX states that its proprietary Index Price uses multiple weighted sources, including:

- stock and ETF prices sourced via Pyth,
- equity-linked RWA token prices from different exchanges,
- equity futures prices from other venues.

When equity markets are closed, OKX retains the last available TradFi price and constrains the live Index Price to within **±10%** of that reference.

This demonstrates a production pattern that combines:

```text
multi-source off-hours price discovery
                +
        explicit safety bounds
```

The key insight is that the industry is not choosing between “stale price” and “synthetic price” in a binary way. Production systems can combine inference with conservative controls.

Source:

- [OKX — How Stock and Commodity X-Perps Work](https://www.okx.com/en-us/help/how-do-stock-and-commodity-x-perps-work)

### 5.4 Kamino: oracle aggregation and protocol-side risk management

Kamino further reduces the whitespace around generic price-quality monitoring.

Its open-source **Scope** oracle aggregator copies prices from multiple oracle sources and validates them against configured rules before updates are accepted. Public Scope releases show support for functionality including:

- Pyth Lazer integration,
- ChainlinkX support for xStocks,
- TWAP windows,
- configurable reference-price tolerance,
- capped / conditional oracle structures.

Separately, Kamino's risk framework monitors the broader risks of lending markets, including liquidity, volatility, liquidation conditions and protocol exposure.

Therefore Valtide should not position itself as:

- “multi-oracle aggregation,”
- “basic price validation,”
- “a generic risk score,”
- “a better Kamino risk dashboard.”

Sources:

- [Kamino Scope](https://github.com/Kamino-Finance/scope)
- [Kamino Scope Releases](https://github.com/Kamino-Finance/scope/releases)
- [Kamino — xStocks Vaults Launch on Kraken](https://kamino.com/blog/xstocks-vaults-launch-on-kraken-powered-by-kamino)

### 5.5 Morpho: configurable oracle and curator model

Morpho markets rely on a selected oracle and market risk parameters rather than a universal Morpho price model. Curators and market creators are responsible for choosing infrastructure and managing exposure.

This creates a natural user for independent model validation: the party choosing and monitoring the production setup.

It also means Valtide should avoid claiming that one universal valuation or LTV is “correct” for every protocol.

Sources:

- [Morpho — Oracle](https://docs.morpho.org/learn/concepts/oracle/)
- [Morpho — Collateral, LTV & Health](https://docs.morpho.org/developers/borrow/concepts/ltv/)
- [Morpho — Ondo Case Study](https://morpho.org/stories/ondo)

### 5.6 X Layer RWA and market-data infrastructure

OKX has described Chainlink Data Streams as available on X Layer mainnet for high-speed market data, including 24/5 equities and tokenized-treasury pricing. The same official context identifies collateral valuation and automated risk-management applications as relevant uses.

This matters to Valtide's positioning. X Layer already provides market-data and RWA infrastructure that applications can build on. Valtide adds an independent validation and control layer for those applications:

```text
X Layer market / RWA infrastructure
                +
       Valtide independent evidence
                ↓
       configurable policy control
```

Valtide complements existing data infrastructure rather than replacing Chainlink, Pyth or OKX pricing products. Where technically accessible, a Chainlink equity Data Stream on X Layer may serve as the reference under test, external comparison evidence, or a live ecosystem integration. The benchmark methodology must preserve independence when the stream is being evaluated.

The [OKX Dev Day 2026 Builder Kit](https://www.okx.com/learn/okx-dev-day-builder-kit) makes working X Layer integration part of the Build a Market context. Valtide implements that attestation, policy-evaluation, and reference-consumer flow as a thin testnet control plane. The deployment is a hackathon reference integration, not audited production infrastructure.

Source:

- [OKX — Chainlink Data Streams on X Layer](https://web3.okx.com/learn/xlayer-chainlink-data-streams)

---

## 6. Competitive Landscape

| Layer | Existing examples | What it answers | Valtide stance |
|---|---|---|---|
| Raw / low-latency market data | Chainlink, Pyth Pro, traditional vendors | “What are markets printing?” | Input, not core competition |
| Constructed 24/7 reference | Pyth Indices | “What continuous reference should exist?” | Strong benchmark / evidence source |
| Hybrid derivative index | OKX X-Perps | “How do we construct and bound an always-on trading index?” | Strong benchmark / comparable architecture |
| Oracle aggregation / validation | Kamino Scope | “Which oracle update should the protocol accept?” | Adjacent / overlapping |
| Protocol risk analytics | Kamino risk framework, professional curators | “How should lending risk be managed?” | Do not duplicate broadly |
| Lending policy | Curators / governance | “What LTV, cap or allocation should we use?” | Downstream decision |
| **Independent collateral model validation** | No obvious tokenized-equity category leader identified | **“Is our production valuation supported by independent evidence?”** | **Target wedge** |

The remaining opportunity is narrow by design.

Valtide is not claiming that no one validates oracle prices today. The hypothesis is that **tokenized-equity collateral introduces enough cross-market and model disagreement to justify a specialized, independent challenger layer**.

---

## 7. Proposed Wedge

### 7.1 Independent model-validation, not oracle replacement

A production setup may use a conservative Chainlink-based methodology, a Pyth constructed index, an exchange index, or a custom oracle adapter. The generic reference being evaluated is the **reference under test**; a production collateral reference is the preferred real-world instance.

Valtide independently evaluates that reference under test against:

- its own challenger estimate,
- the tokenized-equity market,
- other available external references,
- calibrated uncertainty,
- historical behavior in comparable regimes.

Conceptually:

```text
                    PRODUCTION REFERENCE
                           $190
                             │
                             │ validate
                             ▼
Tokenized market ───────► VALTIDE ◄────── External references
     $185                  │                 Pyth / OKX / etc.
                           │
                           ▼
                 independent evidence range
                       $184 – $187
                           │
                           ▼
                   EVIDENCE: CHALLENGED
```

The challenger model remains important because Valtide needs an independent center of gravity. But the product is no longer “oracle #3.”

### 7.2 Uncertainty is part of the answer

Valtide should not output only a point estimate.

It should expose:

- fair-value estimate,
- prediction interval,
- reference deviation,
- token/reference basis,
- residual token premium/discount,
- Evidence State,
- reason codes,
- historical calibration evidence.

### 7.3 Evidence state is not policy action

The validation result is an **Evidence State**, not a policy recommendation:

- **SUPPORTED** — available independent evidence provides no material reason to challenge the reference under test;
- **INCONCLUSIVE** — evidence is too uncertain, incomplete or inconsistent to support or materially challenge it; or
- **CHALLENGED** — sufficiently strong independent evidence materially conflicts with it.

The curator or consuming protocol then maps the Evidence State to its own Policy Action. This is the missing link between price information and risk action: Valtide makes evidence usable by policy, but does not decide the universal policy itself.

### 7.4 Cross-source disagreement is a feature, not a nuisance

A particularly valuable event is when:

```text
production oracle
≠ Pyth constructed reference
≠ tokenized market
≠ Valtide challenger estimate
```

The purpose of Valtide is not to hide disagreement behind one composite score. It is to make the disagreement **observable, quantified and historically testable**.

---

## 8. Value to the Risk Team

The value proposition should not be:

> “Valtide lets the protocol lend more.”

A risk team may use the same evidence to lend more **or** less.

The more defensible value proposition is:

> **Valtide increases confidence in collateral-valuation decisions by giving risk teams an independent methodology and an auditable view of model disagreement.**

Possible outcomes include:

- confirming that a conservative valuation is justified,
- identifying that a production reference appears stale or unusually conservative,
- identifying that a continuous constructed reference appears aggressive,
- triggering manual review,
- supporting a change in caps or allocation,
- providing evidence for a new market configuration.

The ultimate policy choice remains with the curator or protocol.

The product therefore has two consumption modes:

- **Human:** a dashboard and historical evidence help a risk team validate, diagnose and triage a valuation;
- **Machine:** an X Layer attestation and configurable guard allow a protocol, vault or agent to apply its own policy consistently.

The value is not merely another number. It is an auditable bridge from independent evidence to a curator-defined action.

---

## 9. Why a Third-Party Layer Could Matter

The strongest potential value of Valtide is **independence**, not automation alone.

A production oracle and a production risk team necessarily have their own assumptions. A challenger system is useful only if it is sufficiently methodologically separate to expose model risk.

An institutional analogy is independent model validation: a financial institution does not necessarily replace a production model whenever another model differs. It maintains independent evidence to challenge assumptions, investigate exceptions and validate continued use.

For Valtide, that means the product needs to earn trust through:

- transparent methodology,
- point-in-time-correct backtesting,
- reproducible datasets,
- calibrated uncertainty,
- explicit source provenance,
- honest reporting when the challenger model loses.

A visually polished dashboard without those properties is not defensible differentiation.

---

## 10. Asset Strategy

### Primary research asset: NVDAx

NVDAx remains a useful first research asset because:

- NVDA is sufficiently volatile for off-hours price discovery to be observable,
- NVDAx is part of current tokenized-equity lending/vault products,
- Pyth launch materials included a 24/7 NVDA index, creating a strong external benchmark when historical access is available,
- OKX also supports an NVDA X-Perp, creating another relevant reference architecture.

### Secondary / fallback asset: SPYx

SPYx remains strategically important because:

- it has direct production collateral relevance,
- the underlying ETF is diversified and deeply liquid,
- it provides a lower-idiosyncratic-volatility comparison,
- it is included in current xStocks lending/vault products and OKX X-Perps.

Implementation should prioritize **data accessibility and point-in-time integrity** over attachment to a specific ticker.

---

## 11. Market Attractiveness

### Strengths

- Collateral misvaluation has real financial consequences.
- Tokenized-equity lending is now live in production.
- The asset category is expanding quickly.
- Multiple pricing methodologies now coexist, creating observable model disagreement.
- Risk teams already spend resources validating oracle quality and collateral assumptions.
- Independent model validation is a familiar institutional control concept.

### Weaknesses

- The current buyer base is still small.
- Sophisticated curators can build internal analytics.
- Chainlink, Pyth, OKX and protocol-native risk systems are moving quickly.
- Historical tokenized-equity data are short and fragmented.
- The absence of a dedicated third-party category may reflect market immaturity rather than unmet willingness to pay.

### Current assessment

Valtide is best treated as an **emerging infrastructure hypothesis suitable for experimental validation**, not as an already-proven standalone software market.

---

## 12. Falsification Criteria

The current thesis should be weakened or dropped if the project finds that:

- simple production-oracle controls already surface the same events,
- Kamino/KRAF-style monitoring already provides equivalent independent insight,
- the challenger estimate adds no useful information beyond raw token prices or simple blends,
- Pyth / OKX constructed references dominate the model without useful residual information,
- validation alerts have high false-positive rates,
- uncertainty is poorly calibrated,
- historical data cannot support point-in-time testing,
- a risk team would not change its review process based on the output.

A negative result is preferable to cosmetic differentiation.

---

## 13. Current Product Thesis

> **Valtide is an independent collateral-valuation control layer for tokenized equities on X Layer. It combines a challenger fair-value model, uncertainty estimates and cross-market evidence to help DeFi risk teams determine whether a reference under test is supported, inconclusive or materially challenged, then make that evidence usable by their own policy.**

Short form:

> **Validate the reference. Understand the evidence. Apply your own risk policy onchain.**

The central research question is now:

> **When production references, tokenized markets and constructed 24/7 prices disagree, can Valtide identify the evidence state of the reference under test well enough for a curator-defined policy to act consistently?**

---

## 14. Key Sources

### Tokenized-equity market and lending
- [xStocks](https://xstocks.com/)
- [Kamino — xStocks Vaults Launch on Kraken](https://kamino.com/blog/xstocks-vaults-launch-on-kraken-powered-by-kamino)
- [Morpho — Ondo Case Study](https://morpho.org/stories/ondo)
- [Morpho — How Tokenized Stocks Fit Into Onchain Credit](https://morpho.org/blog/how-tokenized-stocks-fit-into-onchain-credit)

### Continuous pricing / benchmarks
- [Pyth — Introducing 24/7 Indices](https://www.pyth.network/blog/24-7-finance-needs-24-7-price-infrastructure-introducing-pyth-indices)
- [Pyth Indices](https://www.pyth.network/products/pyth-indices)
- [OKX — How Stock and Commodity X-Perps Work](https://www.okx.com/en-us/help/how-do-stock-and-commodity-x-perps-work)
- [Chainlink — 24/5 U.S. Equities Streams](https://chain.link/blog/chainlink-24-5-us-equities-streams)

### Lending / oracle infrastructure
- [Kamino Scope](https://github.com/Kamino-Finance/scope)
- [Kamino Scope Releases](https://github.com/Kamino-Finance/scope/releases)
- [Morpho — Oracle](https://docs.morpho.org/learn/concepts/oracle/)
- [Morpho — Collateral, LTV & Health](https://docs.morpho.org/developers/borrow/concepts/ltv/)
