# Frontend Plan

> Curator-facing dashboard for Valtide. Owner: Valerie (`@valeriexylim`).
> This document is the implementation contract between the frontend and the
> backend API. It maps every screen to a real endpoint and defines the demo.

Valtide is a **validation control layer**, not an oracle or a DeFi dashboard.
The frontend's single job is to make one thing legible and trustworthy:

> Given a tokenized equity (NVDAx) and a *reference under test* (the price a
> protocol is currently trusting), is that reference still **SUPPORTED** by
> independent market evidence, **INCONCLUSIVE**, or **CHALLENGED** — and what
> Policy Action would the curator's configured policy return?

Keep the product focused on **model validation**. Resist turning it into a
generic price/portfolio dashboard.

---

## 1. Recommended stack

```text
Vite + React + TypeScript + Tailwind CSS
recharts            the time-series escalation chart in View 3 ONLY
(custom SVG)        the reference number-line in View 2 — see §4A, do NOT use recharts
@tanstack/react-query   data fetching + refetch/freshness (see §4B)
zod (optional)      only if you want runtime response validation; a plain typed
                    fetch wrapper is perfectly adequate for this small endpoint surface
```

Rationale: fastest path to a polished, static-deployable demo; no SSR needed
because the app is a thin client over the FastAPI backend. Deploy as static
assets (Vercel/Netlify/`vite preview`).

**Target viewport: presentation, not mobile.** This is shown on a projector and
recorded. Design large-screen first (≥1280px), large type, high contrast. Mobile
responsiveness is out of scope for the demo.

Suggested layout under `apps/web`:

```text
apps/web/
  src/
    api/            typed client + response types (mirror §3)
    components/     EvidenceChip, ReferenceNumberLine, IntervalBand, ReasonCodes …
    views/          ValidationOverview, ReferenceComparison, HistoricalReplay
    lib/            formatting (pct, σ, timestamps, session labels)
    App.tsx
  .env              VITE_API_BASE_URL=http://localhost:8000
```

The backend already enables CORS for the browser app (`apps/api/valtide_api/main.py`),
driven by `settings.cors_origin_list` — add the web dev origin there if needed.

---

## 2. Backend API surface (already implemented)

All routes are prefixed `/api`. Base URL defaults to `http://localhost:8000`.
Run the backend with:

```bash
uvicorn valtide_api.main:app --reload --port 8000
```

Interactive schema is always available at `/docs` (OpenAPI) — treat that as the
source of truth; the shapes in §3 are copied from `apps/api/valtide_api/models.py`.

| Method | Path | Purpose | Frontend use |
| ------ | ---- | ------- | ------------ |
| GET | `/health` | liveness | boot check |
| GET | `/api/assets` | supported assets + sources | asset selector |
| GET | `/api/valuation/{asset}` | latest **persisted/warmed** result (never advances filter) | primary operational overview |
| GET | `/api/valuation/{asset}/live` | on-demand cold-start diagnostic (needs keys; 503 if unavailable) | optional "run live diagnostic" |
| GET | `/api/history/{asset}?limit=N` | successful warmed scheduler observations only | operational timeline |
| GET | `/api/replay/{asset}?source=panel` | point-in-time historical panel sequence | Historical investigation |
| GET | `/api/replay/{asset}?source=scenario&scenario=weekend_divergence` | deterministic scenario sequence | **Demo only** |
| GET | `/api/backtest/{asset}?source=historical` | historical MAE / RMSE / coverage / state counts | Historical Model Evidence panel |
| GET | `/api/runtime/{asset}` | warm scheduler status | freshness / status strip |
| GET | `/api/onchain/{asset}` | deployed Registry, RiskGuard policy, and evaluation | X Layer Control Plane |
| GET | `/api/onchain/{asset}/enforcement` | read-only DemoVault enforcement check | consumer enforcement status |
| POST | `/api/publish/{asset}` | backend-controlled X Layer attestation publication | not called by the browser |

`/api/replay/{asset}` query params: `source=auto|panel|scenario`,
`scenario=weekend_divergence` (default), optional `timestamp=<ISO>` to return a
single step. It also sets an `X-Valtide-Source` response header. The frontend
must verify `historical_panel` before rendering panel data as historical.

**Degraded states are first-class, not errors.** `GET /valuation/{asset}` returns
`503 data_unavailable` when the warmed runtime has no persisted result; render
"Runtime not warmed yet" and do not substitute the cold-start diagnostic. The
`/live` endpoint is a one-off, read-only diagnostic and returns `503` when a live
input is missing. X Layer status is read through the deployed control-plane
endpoints; publication is backend-controlled, the browser never holds the
publisher signer, and the frontend only observes publication and
synchronization state.

### Operational workflow

The frontend represents the final risk-control workflow rather than a contract
debugger:

```text
Operational Validation
        ↓
backend-controlled onchain synchronization
        ↓
ValtideValidationRegistry
        ↓
RiskGuard policy evaluation
        ↓
DemoCollateralVault enforcement
```

The warmed result from `/api/valuation/{asset}` is the current operational
evidence. The Registry attestation from `/api/onchain/{asset}` is a separate
generation and is compared by observation timestamp and Evidence State. The
frontend must distinguish `SYNCED`, `BEHIND`, `NO_ATTESTATION`, and `MISMATCH`;
Registry freshness is not synchronization. When the generations differ, show
the current operational Evidence State separately from the currently enforced
onchain Policy Action.

Policy configuration belongs to the consuming protocol or curator. The current
hackathon frontend reads the deployed policy and does not edit it. The browser
does not publish attestations or hold a signer key. Scheduler-owned publication
is backend-controlled; RuntimeStatus exposes delivery attempts and outcomes, and
the frontend observes publication/synchronization rather than initiating it.
`DemoVault` is a reference consumer demonstrating composability, not the Valtide
product itself.

### Three data lanes

The UI keeps these lanes explicit and never silently substitutes one for another:

- **Operational monitoring** uses `/api/valuation/{asset}`, `/api/runtime/{asset}`,
  `/api/history/{asset}`, and current `/api/onchain/{asset}` read paths.
- **Historical investigation** uses `/api/replay/{asset}?source=panel` and
  `/api/backtest/{asset}?source=historical`.
- **Deterministic Demo** uses `/api/replay/{asset}?source=scenario` with the
  bundled fixture as an explicitly labelled Demo-only fallback.

Operational history is successful warmed runtime output, not a model backtest.
Historical panel output is research evidence, not current operational history or
historical chain state. Scenario output is illustrative behavior only.
The operational timeline requests up to 12/72/288/2016 successful observations
for 1H/6H/24H/7D, then filters those rows by the actual trailing wall-clock
window anchored to the latest returned observation. It never invents rows or
interpolates scheduler gaps.

### Observation contexts

The same UI components may inspect different kinds of evidence, but the context
must remain explicit:

- **Current operational** — the latest warmed result may be compared with the
  current Registry/RiskGuard generation and current consumer enforcement.
- **Prior operational** — a selected older `/history` result is mapped through
  the current curator policy for inspection only; it must not claim historical
  Registry state, RiskGuard action, or DemoVault enforcement.
- **Historical panel** — a point-in-time research result is mapped through the
  current policy as a counterfactual only; it has no historical chain-state
  claim.
- **Scenario** — deterministic or fixture data may show a policy projection,
  but never drives or represents the deployed control plane.

The deployed X Layer panel remains a current read-only control-plane view when
the selected evidence is prior, historical, or scenario data, and is labelled
accordingly.

---

## 3. Data shapes

`ValuationResult` (returned by `/valuation`, `/valuation/live`, and as a list by
`/replay`) is the object every view is built from:

```ts
type EvidenceState = "SUPPORTED" | "INCONCLUSIVE" | "CHALLENGED";

interface ValuationResult {
  asset: string;
  timestamp: string;              // ISO UTC
  market_state: string;           // regular|premarket|afterhours|overnight|closed

  last_trusted_reference: number; // R0 — the trusted anchor (e.g. stale close)
  token_price: number | null;     // tokenized market (NVDAx)
  token_source: string | null;
  token_observed_at: string | null;
  token_volume: number | null;
  token_volume_usd: number | null;
  token_liquidity_usd: number | null;
  external_constructed_reference: number | null; // optional Pyth-style comparator

  valtide_fair_value: number;     // challenger point estimate
  fair_value_lower: number;       // interval band (may be asymmetric)
  fair_value_upper: number;
  interval_coverage_target: number; // e.g. 0.90

  observed_token_move_pct: number | null;
  model_implied_move_pct: number;
  residual_premium_discount_pct: number | null; // NOT automatically mispricing

  reference_under_test: number | null;          // the price being validated
  reference_under_test_source: string;
  reference_under_test_ts: string | null;
  reference_under_test_age_seconds: number | null; // source lag at observation, not current result age
  reference_deviation_pct: number | null;       // ref vs. fair value
  standardized_deviation: number | null;        // log-space z-score (σ)

  evidence_state: EvidenceState;
  reason_codes: string[];         // e.g. REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL

  confidence: number | null;      // intentionally null in P0
  model_id: string;
  model_version: string;
  interval_semantics: string;
  interval_calibration_type: string;
  interval_calibration_source: string;
  reference_age_seconds: number; // trusted anchor age at observation, not current result age
  source_provenance: Record<string, string>;
}
```

Supporting shapes: `AssetInfo { asset, token_source, underlying_source, model_available }`,
`BacktestMetrics { asset, source, n_observations, evidence_state_counts, n_evaluable, mae, rmse, interval_coverage, window_start, window_end, model_id, model_version, note }`,
`RuntimeStatus { asset, scheduler_enabled, has_state, has_live_result, last_state_timestamp, last_result_timestamp, last_tick_status, last_tick_attempt_at, last_error, last_gap_steps, auto_publish_enabled, last_publish_status, last_publish_attempt_at, last_publish_observation_ts, last_published_observation_ts, last_published_at, last_publish_tx_hash, last_publish_error }`.

The X Layer read models are:

```ts
interface OnchainPolicy {
  max_age: number;
  on_supported: "ALLOW" | "MONITOR" | "REQUIRE_REVIEW" | "RESTRICT_NEW_RISK";
  on_inconclusive: "ALLOW" | "MONITOR" | "REQUIRE_REVIEW" | "RESTRICT_NEW_RISK";
  on_challenged: "ALLOW" | "MONITOR" | "REQUIRE_REVIEW" | "RESTRICT_NEW_RISK";
  on_stale: "ALLOW" | "MONITOR" | "REQUIRE_REVIEW" | "RESTRICT_NEW_RISK";
}

interface OnchainEvaluation {
  evidence_state: EvidenceState;
  policy_action: string;
  exists: boolean;
  fresh: boolean;
}
```

The UI also derives a typed sync status by comparing the operational result's
`timestamp` and `evidence_state` with the Registry attestation's `observedAt`
and Evidence State:

```text
SYNCED         timestamps and Evidence State match
BEHIND         Registry attestation is older than the operational result
NO_ATTESTATION no Registry attestation exists
MISMATCH       same-time state disagreement or a different/newer generation
```

`fresh` is the RiskGuard/Registry freshness decision. `synced` is whether the
attestation represents the current operational observation; neither is a
substitute for the other.

`/api/onchain/{asset}` also returns the X Layer network/chain ID, Registry,
RiskGuard, and DemoVault addresses, plus attestation timestamps and model
version when an attestation exists. The browser shortens addresses for display.

### Interpretation rules (get these right or the demo misleads)

- **Evidence State is not a Policy Action.** Valtide reports the state; the
  curator's policy maps state → action. Render them as two distinct things.
- The **Policy Action mapping is not frontend-owned**. Read the configured
  curator/application policy from `/api/onchain/{asset}` and display its
  `SUPPORTED`, `INCONCLUSIVE`, `CHALLENGED`, and `STALE` mappings. If Demo mode
  cannot reach that endpoint, an explicitly labelled example demo policy may be
  shown; it must never be presented as the deployed policy.
- `residual_premium_discount_pct` is **not** automatically a mispricing/arb — it
  is the part of the token price the challenger doesn't explain. Label it neutrally.
- `confidence` is `null` in P0 by design. Do not invent a 0–100 score.
- `reference_under_test_age_seconds` is source lag at the observation timestamp;
  `reference_age_seconds` is trusted-anchor age at that observation. Neither is
  the wall-clock age of a persisted operational result.
- Operational observation recency is derived separately from `ValuationResult.timestamp`
  versus the browser clock. Onchain attestation freshness comes only from the
  Registry/RiskGuard response (`fresh`, `registry_fresh`, `validUntil`).

---

## 4A. Visualization — read this before building any chart

**The escalation is tiny in price terms and must be rendered in standardized
units, or the demo will not read on screen.** In the verified demo data the
whole story happens inside a ~$0.90 / 0.5% window: fair value moves 180.00 →
179.11, bands are ~$0.60 wide, the reference is pinned at $180. On a naive
price axis the SUPPORTED frame and the CHALLENGED frame look **identical** —
every marker piles up. The signal that actually escalates is the
**standardized deviation (z), 0σ → 4σ**.

Rule: **plot in band-relative / σ units, not raw price.** Show the raw dollar
values as labels/tooltips, never as the primary spatial encoding.

### The reference number-line (View 2) — custom SVG, not recharts

A single horizontal axis centered on the challenger fair value, scaled so the
interval band is a fixed visual width regardless of the dollar spread:

```text
        │◄────────── challenger calibrated band ──────────►│
   ─────┼──────────────────────●──────────────────────┼───────▲──────►  (σ)
      lower                fair value               upper   ref@180
       -1σ                    0                      +1σ    (+2.5σ = CHALLENGED)
```

- Map each reference to σ from the fair value:
  `x = (price - valtide_fair_value) / bandHalfWidthInPrice`, where the band
  half-width defines ±1 unit. `standardized_deviation` already gives you the
  reference's σ directly — use it.
- Fixed viewport, e.g. −4σ…+4σ, so the reference dot visibly **travels outward**
  and crosses the band edge as state escalates. That crossing is the punchline.
- Plot `last_trusted_reference`, `token_price`, `reference_under_test`, and
  `external_constructed_reference` as labelled dots; shade the band; color the
  region outside the band in the CHALLENGED hue.
- This is ~80 lines of SVG/flex. recharts fights this layout; do not use it here.

### The escalation chart (View 3) — recharts

The implemented time-series uses a numeric UTC epoch-millisecond X axis, the
challenger band as an area (`fair_value_lower..upper`), `valtide_fair_value` as
the primary line, and `reference_under_test` plus the tokenized market as
comparison lines. A chart-only null sentinel breaks every line and the band at
real scheduler gaps; it is never a selectable or persisted observation. Tooltips
and multi-day ticks include full UTC date context. No OHLC candles are fabricated.

## 4B. Freshness & data fetching

Freshness is a set of distinct facts, not a frontend verdict:

- Use react-query with `refetchInterval` on `/api/valuation/{asset}` and
  `/api/runtime/{asset}` (e.g. 15–30s) when in live mode.
- Label the operational result as a **Canonical 5m observation** and show its
  full UTC timestamp. Do not call the window-start timestamp generically stale;
  the scheduler uses a five-minute observation window and a 60-second settlement
  grace period. Show the last scheduler attempt and status separately.
- Display `reference_under_test_age_seconds` as **Reference source lag** and
  `reference_age_seconds` as **Trusted anchor age** at the observation. These
  are not wall-clock freshness thresholds and the frontend must not invent
  `<15m`, `<4h`, or similar risk buckets. Backend reason codes may flag a source
  age; otherwise show the age neutrally.
- Onchain freshness comes only from Registry/RiskGuard fields such as `fresh`,
  `registry_fresh`, and `validUntil`; label the status `RiskGuard fresh/stale`
  or `Registry fresh/stale` rather than using an ambiguous umbrella label.
- The scenario replay is static — no polling; fetch once.

The canonical operational cadence is an exact confirmed OKX OnchainOS NVDAx
five-minute candle with a 60-second settlement grace. The frontend displays the
backend's source provenance and does not replace it with a browser-side
freshness rule. Scheduler-owned publication is backend-controlled and observable
through `RuntimeStatus`; the browser never holds the publisher signer.

## 4. The demo

Use the bundled **`weekend_divergence`** scenario. It is deterministic, needs no
API keys or network, and reruns identically — perfect for a live pitch.

```
GET /api/replay/NVDAx?source=scenario&scenario=weekend_divergence
```

Verified output (6 steps) — the escalation arc **is** the story:

| time (UTC) | evidence state | fair value | calibrated band | ref under test | z |
| ---------- | -------------- | ---------- | -------- | -------------- | --- |
| 14:00 | 🟢 SUPPORTED     | 180.00 | 179.56–180.44 | 180.00 | 0.0σ |
| 14:05 | 🟢 SUPPORTED     | 179.95 | 179.59–180.31 | 180.00 | 0.2σ |
| 14:10 | 🟢 SUPPORTED     | 179.86 | 179.53–180.18 | 180.00 | 0.6σ |
| 14:15 | 🟡 INCONCLUSIVE  | 179.68 | 179.37–180.00 | 180.00 | 1.4σ |
| 14:20 | 🔴 CHALLENGED    | 179.44 | 179.13–179.74 | 180.00 | 2.5σ |
| 14:25 | 🔴 CHALLENGED    | 179.11 | 178.81–179.41 | 180.00 | 4.0σ |

The trusted reference stays pinned at **$180** (a stale weekend close) while the
tokenized market discovers a lower price; the challenger's fair-value band walks
away from $180 and the state escalates green → yellow → red. From 14:15 the
reason codes include `REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL`.

### Demo script (≈90 seconds)

1. **Frame it.** "A lending market is trusting a $180 NVDA reference. Is that
   still supported?" — show the Validation Overview at 14:00, state 🟢 SUPPORTED.
2. **Scrub forward.** Play the replay. The band drifts, z-score climbs; at 14:15
   the state flips 🟡 INCONCLUSIVE (reference now outside the interval).
3. **The break.** At 14:20 → 🔴 CHALLENGED, z = 2.5σ. Point at the number-line:
   $180 is clearly outside the shaded challenger band.
4. **Policy, separately.** The Policy Action panel shows the *curator's* mapping
   turning CHALLENGED → `RESTRICT_NEW_RISK`. Stress: Valtide reports evidence;
   the curator owns the action.
5. **X Layer.** Show the deployed Registry/RiskGuard/DemoVault read-only panel:
   operational-versus-Registry sync state, attestation existence/freshness,
   Evidence State, configured Policy Action, and the consumer enforcement check.
   The browser does not sign or publish; Demo mode must label this as the live
   deployed control plane, not a result driven by the scenario replay.
6. **Credibility.** Flip to Historical Model Evidence backed by
   `/api/backtest/NVDAx?source=historical` for coverage, error metrics, and
   historical Evidence State counts. If unavailable, say so; never substitute
   scenario counts as performance evidence.

### The benchmark reveal — bind it to real data or cut it

The "reveal the later benchmark" beat only exists where there is future ground
truth. The `weekend_divergence` **scenario has none** — `ValuationResult` carries
no later NVDA print, so you cannot honestly "reveal" truth from the scenario path.
Two legitimate options:

- **Use the historical-panel path** (`/api/replay/NVDAx?source=panel` and
  `/api/backtest/NVDAx?source=historical`), where the eventual trusted NVDA
  (`underlying_reference`) is the benchmark and `/backtest` computes MAE / RMSE /
  interval coverage against it. This is the only real reveal.
- Otherwise **drop the reveal claim** for the scenario demo and let the escalation
  arc + the `/backtest` metrics panel carry credibility. Do not fake a benchmark.

### Demo resilience — do not depend on a live backend on stage

A pitch that needs `uvicorn` up and CORS behaving is a gamble. Snapshot the
replay responses to a **static JSON fixture** shipped with the app and have the
API client fall back to it when the backend is unreachable:

```bash
curl -s "http://localhost:8000/api/replay/NVDAx?source=scenario&scenario=weekend_divergence" \
  > apps/web/src/fixtures/weekend_divergence.json
```

The Demo lane may use the fixture when the scenario endpoint is unavailable, but
Operational mode must never auto-switch to Demo. The warmed operational result
(`/valuation/NVDAx`) is the primary live view. A **live** variant
(`/valuation/NVDAx/live`) is an explicit cold-start diagnostic only; it is never
silently substituted for operational state or treated as publishable.

---

## 5. Views — implemented vertical slice

The frontend keeps the operational, historical, and demo lanes explicit while
sharing the evidence components below.

**Null-handling is mandatory, not optional.** `token_price`,
`reference_under_test`, `reference_deviation_pct`, and `standardized_deviation`
are all nullable — an INCONCLUSIVE result from `COMPARATOR_UNAVAILABLE` has no
reference at all. Every view needs a defined empty state: the number-line simply
omits a missing dot, deviation/σ render as "—", and the overview says *why*
(reason code) rather than showing a blank or `NaN`. Test with a null-reference
result explicitly.

### View 1 — Validation Overview (hero) — P0
One screen answering all six PRD questions:
1. reference under test, 2. independent references, 3. Valtide estimate,
4. uncertainty, 5. Evidence State, 6. configured Policy Action.

Layout: big **EvidenceChip** (color-coded), fair value ± band, `reference_deviation_pct`
and `standardized_deviation` prominent, **ReasonCodes** list, a distinct
**Policy Action** card, and a status strip (market_state, reference age, model_version).

### View 2 — Reference Comparison — P0
A single horizontal **number-line**: shaded challenger band
(`fair_value_lower..upper`) with `valtide_fair_value` marked, and each reference
(`last_trusted_reference`, `token_price`, `reference_under_test`,
`external_constructed_reference`) as a labelled dot. The point: make it *obvious*
when the reference under test sits outside the band. Do not hide disagreement in
a composite score.

### View 3 — Deterministic Scenario Replay — P0
Scrubber + play control over the scenario sequence; animate the Evidence State
progression and the band walking away. The scenario demonstrates behavior but has
no empirical future ground truth and is not a performance track record.

### View 4 — Basis Analysis — P0-lite / P1
The **DIAGNOSE** job ("why do they disagree?") is the product's moat over a dumb
red/green oracle — do not fully defer it. Ship a **compact basis summary inside
View 1 as P0**: `reason_codes` rendered as human-readable chips plus one line of
`observed_token_move_pct` vs `model_implied_move_pct` and
`residual_premium_discount_pct`. The **full** Basis Analysis view (source ages,
market session, liquidity context, richer breakdown) is P1.

### View 5 — Historical Model Evidence
From `/api/backtest?source=historical`: MAE / RMSE, interval coverage,
Evidence State counts, and the backend caveat. If the historical source is
unavailable, show an explicit unavailable state; never substitute scenario
counts.

---

## 6. Design guidance

- **Evidence encoding must be redundant, never color-only.** The EvidenceChip is
  the app's anchor element and pairs **icon + text label + color**: SUPPORTED =
  green/check, INCONCLUSIVE = amber/dash, CHALLENGED = red/alert. Color-only fails
  colorblind viewers and bad projectors — unacceptable in a validation product.
  Verify contrast at projector quality; the same triad must be used everywhere.
- Always show **provenance & freshness** (source, timestamp, age, market_state).
  Trust is the product; hide nothing.
- Render **degraded states deliberately** (runtime not warmed, onchain status
  unavailable, historical evidence unavailable, live inputs missing) rather than
  as failures.
- **Two-column mental model** in every relevant place:
  *Evidence (Valtide)* on the left, *Action (curator policy)* on the right.
- Format helpers: percentages to 2dp, σ to 1dp, timestamps as UTC, collapse
  premarket/afterhours into an "extended" badge if desired.

---

## 7. Current implementation handoff

The frontend is implemented as three explicit lanes for NVDAx:

- **Operational:** `/api/valuation/{asset}`, `/api/runtime/{asset}`,
  `/api/history/{asset}`, `/api/onchain/{asset}`, and
  `/api/onchain/{asset}/enforcement`. The warmed result is primary; `/live` is
  a cold-start diagnostic only. Operational history uses real timestamp windows,
  numeric UTC chart positions, visible gap breaks, and a latest-point reset.
- **Historical:** `/api/replay/{asset}?source=panel` and
  `/api/backtest/{asset}?source=historical`. The panel defaults to its latest
  point, supports full UTC dates for multi-day investigation, and makes no
  historical Registry/RiskGuard/DemoVault claim.
- **Demo:** `/api/replay/{asset}?source=scenario` with an offline fixture
  fallback. It starts at scenario step one, makes no performance claim, and
  never drives the deployed X Layer state.

The implementation keeps Evidence State separate from curator Policy Action,
uses exact backend reason codes, displays dynamic calibrated-interval targets,
and leaves source-age classification to backend evidence quality and RiskGuard
freshness. NVDAx is the only live asset; there are no fabricated assets, OHLC
candles, or browser publication controls. The read-only control-plane workflow
is:

```text
Operational Validation
        ↓
backend-controlled synchronization / publication status
        ↓
ValidationRegistry
        ↓
RiskGuard policy evaluation
        ↓
DemoCollateralVault reference-consumer enforcement
```

Valerie's remaining scope is visual presentation: theme, typography, spacing,
chart aesthetics, motion, responsive refinement, and recording polish. Those
choices should not change the data-lane, policy, freshness, or publication
semantics above.
