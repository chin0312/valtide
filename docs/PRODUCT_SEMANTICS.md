# Valtide Product Semantics

This document is the as-built data-context and interpretation contract for the
Valtide dashboard. It describes what each visible context means and what the
browser may claim from the backend. It is not a UI implementation plan.

Valtide is a validation control layer, not an oracle replacement. The frontend
does not calculate Evidence State, reason codes, model values, or policy
semantics.

## Core Ownership Boundary

```text
Valtide backend        → Evidence State and reason codes
Curator / protocol     → Policy Action mapping
Consumer               → Enforcement
Browser                → Read-only observation and explanation
```

The canonical Evidence States are `SUPPORTED`, `INCONCLUSIVE`, and
`CHALLENGED`. Policy Actions are configured by the consuming application and
are not recommendations made by the frontend.

## Three Explicit Data Contexts

Operational, Historical, and Demo are separate lanes. The frontend must never
silently substitute one for another.

### Operational

Operational mode uses the warmed runtime as its primary source:

- `GET /api/valuation/{asset}` — latest persisted operational result;
- `GET /api/runtime/{asset}` — scheduler, persistence, and publication status;
- `GET /api/history/{asset}` — successful warmed observations; and
- `GET /api/onchain/{asset}` plus `/enforcement` — current deployed control
  plane state.

The `/api/valuation/{asset}/live` endpoint is a cold-start, read-only
diagnostic. It must never silently replace an unavailable warmed result.

Operational scheduler gaps remain gaps. The frontend does not interpolate,
forward-fill, or create observations.

### Historical

Historical mode uses:

- `GET /api/replay/{asset}?source=panel`; and
- `GET /api/backtest/{asset}?source=historical`.

The replay response must expose `X-Valtide-Source: historical_panel`. The
frontend fails closed when the provenance header is missing or unexpected; it
does not render an unverified response as historical evidence.

Historical panel observations are research evidence, not operational history
and not historical Registry, RiskGuard, or DemoVault state. Historical policy
labels are counterfactual mappings through the current configured policy.

Historical model evidence reports observations, evaluable points, MAE, RMSE,
interval coverage, and Evidence State distribution. These are diagnostics, not
production guarantees.

### Demo

Demo mode uses the backend-owned `weekend_divergence` scenario. It contains
exactly six canonical five-minute observations. A bundled fixture is available
only as an explicitly labelled Demo fallback when the scenario endpoint is
unavailable.

Demo playback may show the progression:

```text
SUPPORTED → INCONCLUSIVE → CHALLENGED
```

Scenario policy text is a projection using the current policy configuration.
The scenario is not published to X Layer, does not drive the deployed Registry,
and is not historical performance evidence. The live X Layer panel remains
clearly labelled as current deployed state, not scenario state.

## Current, Prior, and Selected Observations

- **Current operational observation** may be compared with the current Registry,
  RiskGuard evaluation, and consumer enforcement when their generations are
  synchronized.
- **Prior operational observation** is an older warmed result. It may be shown
  with the current policy mapping, but it must not claim historical onchain
  enforcement.
- **Historical panel observation** is a point-in-time research result. It has no
  historical chain-state claim.
- **Scenario observation** is deterministic demonstration data only.

The operational result and Registry attestation can temporarily differ. The
frontend compares their observation timestamps and Evidence States and reports
`SYNCED`, `BEHIND`, `NO_ATTESTATION`, or `MISMATCH`. Registry `fresh` describes
attestation freshness; it does not prove synchronization with the latest
operational result.

## Freshness and Timing

The UI keeps these concepts distinct:

- operational observation recency — wall-clock age of the selected result;
- reference-under-test source lag — age at the valuation observation;
- trusted-anchor age — age of the underlying anchor at that observation; and
- Registry/RiskGuard freshness — onchain validity and policy `maxAge`.

None of these display values changes Evidence State or RiskGuard semantics.

## Backend Response Contract

The frontend consumes the backend response fields without renaming or
recomputing them. The main read paths are:

| Context | Endpoint | Meaning |
|---|---|---|
| Operational result | `/api/valuation/{asset}` | latest warmed persisted result |
| Live diagnostic | `/api/valuation/{asset}/live` | one-off cold-start diagnostic |
| Operational history | `/api/history/{asset}` | successful warmed scheduler results |
| Historical replay | `/api/replay/{asset}?source=panel` | causal historical panel sequence |
| Demo replay | `/api/replay/{asset}?source=scenario` | six-observation deterministic scenario |
| Historical metrics | `/api/backtest/{asset}?source=historical` | historical diagnostics |
| Runtime | `/api/runtime/{asset}` | scheduler and publication status |
| X Layer | `/api/onchain/{asset}` | current Registry and RiskGuard read state |
| Enforcement | `/api/onchain/{asset}/enforcement` | read-only reference-consumer check |

`POST /api/publish/{asset}` is not called by the browser.

## X Layer Workflow

The user-facing workflow is:

```text
Operational validation
        ↓
backend-controlled publication / synchronization
        ↓
ValtideValidationRegistry
        ↓
curator-owned RiskGuard policy
        ↓
DemoCollateralVault or another consumer
```

The browser observes the deployed control plane and never holds the publisher
signer, edits policy, signs transactions, or publishes attestations. The
current hackathon frontend reads the deployed policy rather than editing it.
`DemoCollateralVault` is a reference consumer demonstrating composability; it
is not the Valtide product or a production lending protocol.

## Display Integrity Rules

- Show exact backend timestamps and preserve UTC spacing.
- Keep missing measurements unavailable rather than fabricating values.
- Use calibrated interval bounds for interval comparisons; do not infer them
  from a generic statistical threshold.
- Keep Evidence State, Policy Action, and Enforcement visually distinct.
- Do not label scenario counts as track record, accuracy, or historical
  performance.
- Do not render synthetic OHLC or candlesticks when the backend provides point
  observations only.
- Keep source provenance and model/calibration metadata visible where useful.

## Degraded States

Unavailable operational state is shown as unavailable or “Runtime not warmed
yet”; it does not fall back to Demo. Historical provenance failure is shown as
unavailable historical evidence. A missing or stale onchain attestation is
shown separately from an offchain Evidence State. These are honest product
states, not frontend errors to hide.
