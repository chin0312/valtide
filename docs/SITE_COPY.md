# Site copy for valtide-liard.vercel.app

Replaces the current fluff. Leads with the on-chain gate, same as the pitch. Short
sentences, concrete claims. No model mechanism on the page — that lives in PRODUCT.md.

---

## Hero

**Headline:** The brakes for tokenized-stock lending.

**Subhead:** Tokenized stocks trade 24/7. The real stock is closed nights and weekends.
When the on-chain price drifts, Valtide stops the lending protocol from trading on it —
on-chain, automatically.

**Buttons:** [Watch it block a borrow] [How it works]

---

## The gap

Tokenized stocks trade around the clock. The stock behind them doesn't. For most of the
week the real market is closed, so the on-chain price runs on thin pools and a stale
reference. A lending protocol that takes one of these tokens as collateral keeps lending
and liquidating against a price that's drifted from the real company.

This market is young, so it hasn't blown up yet. Every new collateral type works until the
first time it doesn't. We build the brakes before that day.

---

## What Valtide does

Valtide is an on-chain gate between a tokenized-stock price and a lending protocol. When
the price can't be trusted, the gate tells the protocol to stop.

It marks every price one of three ways:

- **SUPPORTED** — safe to use.
- **INCONCLUSIVE** — too thin or stale to say. We don't guess.
- **CHALLENGED** — don't lend against this.

The verdict is written to X Layer. A vault reads it and blocks new borrowing on a
challenged price. No governance vote, no waiting for Monday.

---

## Why it's independent

A protocol won't trust a price check it runs on itself, and it won't trust one from a
competitor. Valtide is a neutral third party. Every verdict is public and auditable on X
Layer. Nobody holding these positions marks their own homework.

---

## Live on X Layer

Deployed on X Layer testnet. The registry stores each verdict, the risk guard turns it into
an action, the demo vault blocks borrowing on a challenged price. Every decision is a hash
you can replay.

- ValtideValidationRegistry — `0x1A53...B635`
- ValtideRiskGuard — `0x8e17...0CE7`
- DemoCollateralVault — `0x4beC...49ce`

(Link each to the X Layer explorer.)

---

## Who it's for

Protocols holding tokenized stocks as collateral: lending vaults, treasury agents, yield
products. If you price a 24/7 token against a market that's closed half the week, you need
a gate that stops the trade when the price can't be trusted.

---

## Where we go

Stocks are the start. The same gap hits tokenized bonds, commodities, and every real-world
asset coming on-chain. We want to be the validation and halt layer for all of them on X
Layer.
