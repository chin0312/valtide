# Valtide — 3-minute pitch

Format: 3 minutes, hard stop. Then 1–2 minutes of questions. Show the product live.
Judges: VCs, partners, OKX staff.

Rules for this pitch:
- Lead with the on-chain gate. That's the product. The model is how it decides, not the
  headline. Keep Kalman filters, z-scores, and calibration out of the 3 minutes.
- Don't claim better price accuracy. We barely beat the raw token price and we know it.
- Don't apologize. State what we do, show it live, say how we make money.

---

## Script (aim for 2:40, leave buffer)

### The gap (~30s)
Tokenized stocks trade 24 hours a day. OKX lists them on X Layer. But the real stock
behind them is closed every night and all weekend. During those hours the on-chain price
drifts — thin pools, no fresh reference, nothing anchoring it to the real company.

A lending protocol that takes one of these tokens as collateral keeps lending and
liquidating against that drifting price. This market is young, so it hasn't blown up yet.
Every new collateral type works until the first time it doesn't. We want the brakes in
place before that day, not after.

### What we built — show it (~80s)
(Switch to the live dashboard. Drive it, don't narrate slides.)

Valtide is an on-chain gate between a tokenized-stock price and a lending protocol. When
the price can't be trusted, the gate tells the protocol to stop.

Watch. Here's a weekend where the token price pulls away from the real stock. Valtide
marks the price CHALLENGED and writes that to our contract on X Layer. (Show the state
flip.)

The vault reads that state and blocks the new borrow. (Show the revert.) The protocol
wrote the rule, not us — on a challenged price it chose to stop new borrowing. It could
also have chosen to just monitor, or require a review. We report the state; the protocol
owns the response.

And every decision is a hash on X Layer. Anyone can replay exactly why we challenged the
price. (Show the registry entry.)

This is live on X Layer testnet right now. Registry, risk guard, and a demo vault, all
deployed.

### Why it's us (~25s)
A protocol won't trust a price check it runs on itself, and it won't trust one from a
competitor. The check has to be independent. That's what we are — a neutral third party,
deployed on-chain, where every verdict is public and auditable. Nobody holding these
positions can mark their own homework.

And it compounds. Every protocol we protect sends us more live price data and more real
divergences. That sharpens our calibration, which is the hard part to copy. The more of
this market we cover, the harder we are to replace.

### How we make money (~15s)
Per-protocol subscription. Every lending vault or treasury product that holds tokenized
stocks pays a flat fee for validated, enforced price states. Tokenized real-world assets
on-chain are already [$X billion and growing — insert the current RWA figure before the
pitch; don't guess on stage]. On X Layer specifically that's agents like Aumo and yield
products like Agama — they hold this exposure, so they carry this risk.

### Where we go (~20s)
Stocks are the start. The same gap — a 24/7 token priced against a market that closes —
hits tokenized bonds, commodities, every real-world asset coming on-chain. We want to be
the validation and halt layer for all of them on X Layer.

### Close (~10s)
Tokenized assets are moving on-chain fast. The brakes aren't built yet. We built them, and
they're live on X Layer.

---

## Questions to expect

**"Has anyone actually lost money on this yet?"**
Not that we can point to — the market is too new. That's the point. Risk infrastructure
that ships after the first blowup is too late. We're building it while the collateral is
still small, so it's there when it isn't.

**"Isn't auto-freezing my vault on your flag dangerous? What if you're wrong?"**
We don't freeze anything. We publish a state; the protocol decides what it does with each
one, from just monitoring up to blocking new risk. A cautious protocol can require a human
review on a challenged price instead of a hard stop. We also abstain rather than flag when
the data is thin, so a weak signal becomes INCONCLUSIVE, not a false alarm. And every
calibration is per-asset — we don't point a model tuned on one stock at another and freeze
on it.

**"Why can't Chainlink or an oracle just add this?"**
An oracle's job is to publish a price with high uptime. Ours is the opposite — to refuse to
vouch for a price and stop a trade. That's a different product and a different incentive. An
oracle that frequently says "don't trust my number" is a broken oracle. For us it's the
feature. And we're neutral; we don't sell the price we're checking.

**"The SEC is bringing tokenized stocks under real rules. Doesn't that solve this?"**
Rules fix the legal wrapper and the data quality during market hours. They don't open the
real stock market at 2am on a Sunday. The 24/7-token-versus-closed-market gap stays. If
anything the rules require halt coordination and auditable on-chain enforcement — which is
the thing we do and the regulated venue still has to source from somewhere.

**"Who pays, and how big is it?"**
Per-protocol subscription from any vault or product holding tokenized real-world assets as
collateral. The pool of those protocols is small today and grows with every new RWA
market on X Layer. We're early on purpose.

**"Have any protocols signed up?"**
Not yet — this is where we are. The near-term plan is the protocols already holding this
exposure on X Layer. We have the contracts deployed and a working integration to show
them, which is the conversation we're starting now.

**"How do you know your check is any good?"**
On held-out NVDA data our 90% range covered the truth 94% of the time. Honest limit: we've
verified up to 4-hour gaps, not full weekend closes, and each new asset needs its own
calibration. We'd rather tell you that than oversell it.
