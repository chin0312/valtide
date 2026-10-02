# What Valtide is

One source of truth for the team, the site, and the pitch. Plain answers, real numbers.

## The problem

Tokenized stocks trade 24/7 on-chain. The real stock behind them is closed nights and
weekends. So for most of the week, a protocol holding a tokenized stock as collateral is
pricing it off a market that isn't open. Pools are thin, the reference price is stale, and
nothing tells the protocol how wrong the price might be. When the gap gets large, vaults
liquidate on a price no one can defend.

## What Valtide does

Valtide watches a tokenized-stock price and answers one question: can you trust this price
right now?

It is not an oracle. It does not publish a price. It checks a price against its own
independent estimate and returns one of three verdicts, with a confidence range and a
reason. Then it publishes that verdict on X Layer so a protocol can act on it.

## What it outputs

For each asset and timestamp:

- A state: SUPPORTED, INCONCLUSIVE, or CHALLENGED.
- A fair-value estimate and a calibrated range around it (e.g. a 90% range).
- A z-score: how far the price under test sits from our estimate, in standard deviations.
- Reason codes: why we said what we said. Examples: UNDERLYING_REFERENCE_STALE,
  REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL, TOKEN_MARKET_QUALITY_LOW,
  CALIBRATION_GLOBAL_FALLBACK.
- Provenance: model version, calibration type, data sources.
- On-chain: a hash of the above plus the state, written to the registry on X Layer.

## How it works

1. Collect a snapshot: the token price, the last trusted price of the real stock, the
   current real-stock price if the market is open, timestamps, and pool depth.
2. Estimate fair value. A Kalman filter runs in log-price space on 5-minute steps. It
   takes in the token price to form an estimate, reads the estimate, and only then folds
   in the current real-stock price for the next step. (So the current quote never feeds
   its own check.)
3. Put a calibrated range around the estimate. The range comes from conformal calibration
   fit per market session, so a "90% range" actually covers about 90% in testing.
4. Judge the price under test. Compute the z-score. If it's under 1, SUPPORTED. If it's 2
   or more, CHALLENGED. In between, INCONCLUSIVE.
5. Abstain on bad data. Regardless of the z-score, we return INCONCLUSIVE when the token
   or reference is missing, the reference is stale, the pool is near-dead, the unit scale
   looks wrong, or model uncertainty is too high.
6. Publish to X Layer. The state and an evidence hash go to the ValtideValidationRegistry.
7. Enforce. The ValtideRiskGuard maps the state to an action a vault owns — ALLOW,
   MONITOR, REQUIRE_REVIEW, or RESTRICT_NEW_RISK. The DemoCollateralVault blocks new
   borrowing when the state is CHALLENGED.

## Why it's useful

A lending protocol can't safely hold a 24/7 tokenized stock without knowing when to stop
trusting the price. Valtide gives three things a raw price can't:

- It abstains. It says "we don't know" instead of emitting a confident wrong number.
- It carries honest uncertainty. On held-out NVDA data, the 90% range covered the truth
  94.3% of the time, typical width ~37 bps, fair-value error 6.75 bps MAE / 10.4 bps RMSE
  (n = 11,828).
- It's enforced and auditable. The verdict is on X Layer, and every decision is a hash you
  can replay.

## Strengths

- Calibration is measured, not asserted. The numbers above come from a held-out test set.
- It abstains and gives reason codes. Most oracles never say "unsure."
- The full path from estimate to on-chain enforcement works and is deployed on X Layer
  testnet.
- Decisions are deterministic and replayable; the live and historical paths share the same
  transformation code.

## Weaknesses (say these before a judge finds them)

- Our point estimate barely beats the raw token price — about 10 bps on NVDA. So we don't
  sell accuracy.
- We've verified accuracy up to 4-hour gaps, not full 8-hour-plus weekend closes. Closed
  and overnight periods fall back to a global calibration because there's no real-stock
  price to check against then.
- One asset today (NVDAx), one price source.
- Generalization is unproven. On a stress test with a built-in 25 bps cross-venue basis,
  the model over-flags (23% of normal steps CHALLENGED, coverage drops to 62%), because
  the ranges are tuned to NVDA's own noise. A different venue or a different stock with a
  structural basis needs its own calibration.

## Competitors (they're customers, not rivals)

- Aumo (aumo.finance): an AI treasury agent on X Layer that routes stablecoin yield and
  offers tokenized US-stock pools (NVDA, AAPL, MSFT, META). It holds tokenized-stock
  exposure, so it needs to know when those prices are untrustworthy.
- Agama (agama.finance): a yield layer on tokenized stocks routed into private credit.
  Holds tokenized-stock positions, so it needs honest off-hours valuation.

Neither validates prices or abstains. Both are the kind of protocol that would consume
Valtide. Positioning line: Aumo and Agama put tokenized stocks to work 24/7; Valtide tells
them when the price can be trusted and enforces it on X Layer.

## Deployed contracts (X Layer testnet, chainId 1952)

- ValtideValidationRegistry: 0x1A53C85C66EA212693d36bF842574643C4d9B635
- ValtideRiskGuard: 0x8e17a4eB93074ea74d05D9bc316d85AD3B540CE7
- DemoCollateralVault: 0x4beC6Bc1DF651f36758216cA02db62b5603349ce
