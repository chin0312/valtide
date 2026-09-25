# Valtide Interface Design System

Status: implementation-ready for the hackathon prototype  
Audience: protocol risk teams, collateral curators, and technically curious judges  
Product posture: independent evidence and model validation for tokenized-equity collateral

## 1. Product design thesis

Valtide should feel like an independent risk instrument, not an exchange, an AI assistant, or a generic DeFi dashboard.

The interface must answer four questions in order:

1. **VALIDATE — Is the reference credible right now?**
2. **DIAGNOSE — What explains the difference?**
3. **TRIAGE — Which evidence needs human attention?**
4. **GUARD — What policy action does the protocol take?**

The product's main visual idea is **a measured range and the evidence around it**. The uncertainty band—not a candlestick—is the visual hero. Price candles are contextual evidence behind that band.

The primary screen is a dense, calm control surface. It should feel closer to a lab instrument or institutional risk terminal than a consumer trading app.

## 2. Reference synthesis

### Borrow from Compound / Block Analitica

- Flat, low-contrast dark surfaces.
- Large chart with little decorative chrome.
- Metric and timeframe controls integrated into the chart header.
- Compact KPI row above the chart.
- Muted axes and minimal gridlines.

### Borrow from Sphere

- Clear information zones for benchmarks, chart, filters, and tables.
- Tight row density and right-aligned tabular values.
- Primary value plus small contextual delta on the same baseline.
- Filters stay subordinate to the analysis.

### Borrow from Vercel's system

- Monochrome precision and a strict 4px spacing base.
- Hairline borders, crisp typography, and minimal decoration.
- Clear surface hierarchy without heavy shadows.

### Do not copy

- Sphere's purple tint, rounded card stacks, decorative icons, or green/red performance deltas.
- Compound's use of green/red for ordinary price movement.
- Vercel's marketing gradients, pill-heavy CTAs, large hero sections, or spacious landing-page rhythm.
- Trading-terminal urgency, flashing values, depth charts, or buy/sell affordances.

## 3. Visual direction

Keywords: **forensic, measured, sharp, independent, kinetic, auditable**.

- Dark-first; never pure black.
- Mostly grayscale. State color is sparse and meaningful.
- Controlled rounding: 8–10px on outer instruments, 4–6px on controls, square internal grid divisions.
- Borders establish hierarchy; shadows do not.
- Dense data, generous separation between major regions.
- Left-aligned editorial hierarchy. No centered hero content.
- Visible timestamps and provenance wherever a value can become stale.

## 4. Color tokens

```css
:root {
  color-scheme: dark;

  --bg-canvas: #07090a;
  --bg-surface-1: #0b0e0f;
  --bg-surface-2: #111718;
  --bg-inset: #050708;
  --bg-hover: #162022;

  --border-subtle: #182226;
  --border-default: #253237;
  --border-strong: #3b4d52;

  --text-primary: #f3faf7;
  --text-secondary: #b8c7c2;
  --text-muted: #71837d;
  --text-disabled: #444d59;

  /* Neutral interactive accent; never communicates evidence state. */
  --accent: #affc41;
  --accent-hover: #b2ff9e;
  --accent-soft: #affc4117;

  /* Evidence State only. */
  --state-supported: #1dd3b0;
  --state-supported-soft: #1dd3b015;
  --state-inconclusive: #affc41;
  --state-inconclusive-soft: #affc4115;
  --state-challenged: #d57ade;
  --state-challenged-soft: #3c164266;

  /* Charts are evidence sources, not semantic states. */
  --series-reference: #d8dee6;
  --series-valtide: #91b9ca;
  --series-tokenized: #687786;
  --series-trusted: #59636f;
  --band-fill: #91b9ca1f;
  --market-closed: #ffffff08;
}
```

### Color rules

- Evidence states use a high-chroma spring trio: mint, acid-lime, and lifted plum. Never use traffic-light green/red.
- `#086375` is the deep teal supporting tone for charts and selected analytical surfaces; `#b2ff9e` is a hover/highlight tone, not a large background.
- Ordinary deltas are neutral gray with an explicit `+` or `−` sign.
- Never use green for “price went up” or red for “price went down.”
- Chart series use distinguishable neutral hues and line styles, not status colors.
- Never use gradients, glow, neon, or blurred color fields.
- Do not rely on color alone. Every state also gets text and a distinct marker shape.

## 5. Typography

### Font stack

- **Interface:** `Inter`, fallback system sans.
- **Headings and labels:** `Inter`.
- **Numbers, timestamps, hashes, codes, axes:** `Inter` with tabular numerals, fallback system sans.

Use one clean sans-serif family throughout. Tabular numerals keep live values aligned without a typewriter appearance. Two families is an upper limit, not a requirement.

```css
--font-ui: "Inter", system-ui, sans-serif;
--font-heading: "Inter", sans-serif;
--font-data: "Inter", system-ui, sans-serif;
```

### Type scale

| Role | Size / line | Weight | Tracking | Font |
|---|---:|---:|---:|---|
| Page title | 24 / 30 | 550 | -0.03em | UI |
| Verdict value | 30 / 34 | 550 | -0.035em | UI |
| Primary metric | 26 / 30 | 500 | -0.035em | Data |
| Section title | 13 / 18 | 550 | -0.01em | UI |
| Body | 13 / 20 | 400 | -0.005em | UI |
| Table value | 12 / 18 | 450 | 0 | Data |
| Control | 12 / 16 | 500 | 0 | UI |
| Eyebrow / label | 10 / 14 | 500 | 0.09em | Data, uppercase |
| Caption | 11 / 16 | 400 | 0 | UI |

Rules:

- Use tabular numerals everywhere data can update.
- Keep headings at 550–600 maximum; avoid loud 700–900 weights.
- Use tabular numerals for facts; no monospaced font.
- Currency symbols, unit suffixes, and insignificant decimals render at 60–70% visual emphasis—not a smaller hit target—and in `--text-muted`.
- Deltas sit inline with their value, smaller and neutral: `$190.00  +2.32%`.

### Iconography

- Icons are functional punctuation, never decoration.
- Use a 16px optical box, 1.5px stroke, subtly rounded outer corners, sharp internal joins, and square line terminals.
- Always pair unfamiliar icons with text. Prefer a text label when it is clearer than a symbol.
- Do not place icons in metric tiles or section headings.
- Evidence markers use three distinct geometries as well as color: check/square for supported, split diamond for inconclusive, cross/square for challenged.
- Do not mix icon families. If an icon library is introduced, add only the small reviewed subset used by the product.

## 6. Grid, spacing, and shape

Base unit: 4px.

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;

--radius-xs: 4px;
--radius-sm: 8px;
--radius-md: 10px;
--radius-pill: 999px; /* state chips only */
```

- Desktop content max width: 1480px; page gutters: 24px.
- Main analysis grid: 12 columns, 16px gutters.
- Major section spacing: 24–32px.
- Panel padding: 16px standard, 20px for the primary chart.
- Inputs and buttons: 32px compact, 36px default.
- KPI tiles form one connected grid with shared borders. No gaps and no floating-card shadows.
- Use `1px` borders. Never use more than one shadow level; default is none.

## 7. Information architecture

### Primary navigation and data source

Ship one **Overview**. Do not expose empty Historical, Operational, or Demo pages as primary navigation.

- Prefer warmed operational data when it exists.
- Otherwise show the deterministic scenario in the same overview with an unmistakable `DEMO` or `DEMO FIXTURE` source chip.
- Operational history is never interpolated. Demo playback uses continuous visual interpolation between fixed presentation periods; Evidence State and reason codes change only when the playhead crosses a real period boundary.

### Primary screen order

1. App bar and system freshness.
2. A disabled NVDAx asset selector that states the backend's single-asset boundary.
3. Connected KPI strip.
4. Large valuation timeline with a compact horizontal interval plot directly beside it.
5. Compact Evidence, Policy, and Price Basis bento cards.
6. Evidence record with state distribution, transitions, and source facts.
7. X Layer provenance pipeline, including a legible read-only state when the API is unavailable.

This order maps directly to VALIDATE → DIAGNOSE → TRIAGE → GUARD.

## 8. Desktop layout

```text
┌ VALTIDE ─ OVERVIEW ───────────────────────────── source / backend status ┐
├ Reference ┬ Fair value ┬ Token ┬ Deviation ┬ Sigma ┬ Last trusted ──────┤
├ LARGE VALUATION TIMELINE + BAND ───────────┬ HORIZONTAL PRICE RANGE ──────┤
├ Evidence ─────────┬ Policy ────────────────┬ Price basis ────────────────┤
├ EVIDENCE RECORD / STATE DISTRIBUTION / SOURCE FACTS ──────────────────────┤
└ X LAYER PROVENANCE PIPELINE ──────────────────────────────────────────────┘
```

Do not imply multi-asset selection while the backend supports only NVDAx. Show the real boundary rather than fake queue items.

## 9. Core components

### 9.1 Evidence Verdict

This is the strongest visual element.

- Left: label `EVIDENCE STATE`, state word, one-sentence explanation.
- Right: deviation in `%`, `bps`, and `σ`, plus attestation timestamp.
- A 2px state-color rule runs along the left edge; the rest stays neutral.
- Include plain language: `Reference $190.00 is 2.4σ above Valtide's expected range of $184.20–$187.20.`
- Do not say “bad price,” “wrong,” “fraud,” or “mispricing.”

### 9.2 Policy Result

Always visually separate from Evidence Verdict by a border and its own heading.

- Label: `POLICY RESULT`.
- Value: `RESTRICT_NEW_RISK`, `REQUIRE_REVIEW`, or `ALLOW`.
- Caption the source of the decision: `Configured protocol rule—not a Valtide recommendation.`
- Show the matched rule in compact text.

### 9.3 Price snapshot

Four connected cells:

- Reference under test.
- Valtide fair value with range beneath.
- Tokenized market price with spread/depth beneath.
- Last trusted reference with age beneath.

No icons. Every cell includes source and as-of time in a tooltip or caption.

### 9.4 Main chart

Layers, from back to front:

1. Market-closed shading.
2. Valtide uncertainty band.
3. Tokenized-market candles or fine line.
4. Valtide fair-value line.
5. Last-trusted reference, horizontal and visibly stale.
6. Reference under test, dashed and strongest.

Rules:

- The decisive moment is where the reference exits the uncertainty band.
- Candles are context, not the hero.
- No vertical gridlines; horizontal guides at no more than four levels.
- 1.5px default series, 2px selected series.
- Chart header: small as-of time → large selected value → controls.
- Metric control: `PRICE / DEVIATION / BASIS`.
- Operational range control: `1H / 6H / 24H / 7D`; default `24H`.
- Use real UTC spacing and break every series at scheduler gaps. Never interpolate missing observations.
- Demo playback uses 26 one-minute presentation frames derived from six backend-owned five-minute anchors.
- Do not render candlesticks until the backend exposes genuine OHLC inputs. The calibrated interval band is the truthful model-native visual.
- Legend supports click-to-isolate and keyboard focus.
- Tooltips show all sources at one timestamp and clearly mark stale/missing values.

### 9.5 Reference comparison

Use a single horizontal price axis with:

- One shaded Valtide range.
- Dots for reference under test, tokenized market, and last trusted value.
- Source, value, age, and distance from range shown in aligned rows.

This makes the outlier obvious without requiring chart literacy.

### 9.6 Basis breakdown

Use a compact waterfall:

`TOKEN MOVE = MODEL-IMPLIED MOVE + UNEXPLAINED BY MODEL`

- Never label the residual “mispricing.”
- Positive and negative bars use neutral light/dark fills, not green/red.
- Include a one-sentence interpretation below the chart.

### 9.7 Market quality

Show only metrics that affect evidence confidence:

- Depth at 50bps.
- 24h volume.
- Bid-ask spread.
- Quote/reference staleness.
- Market-open status.

Each metric gets a plain-English caption or threshold, e.g. `Thin: only $82k within 50bps`.

### 9.8 Reason codes

- Neutral outlined chips: `REFERENCE_OUTSIDE_BAND`, `MARKET_CLOSED`, `LOW_DEPTH`.
- State color appears only on the section's severity marker, not every chip.
- Clicking a code expands a two-line explanation and supporting values.

### 9.9 Onchain provenance

Use a linear verification strip:

`Publisher  →  Registry  →  Curator policy  →  RiskGuard  →  DemoVault`

Below it, show `evidenceHash`, transaction, block, issued-at, valid-until, and network in tabular text. Truncate hashes visually but make the full value copyable.

## 10. Tables

- Header: 10px uppercase text, muted, sticky.
- Body: 12px; 44px rows on desktop.
- Numeric columns are right-aligned and tabular.
- A primary value and its delta may share a cell; delta remains muted.
- Use row dividers, not detached rounded rows.
- Selected row uses a 2px accent rule and subtle `--accent-soft` background.
- Sort controls appear only on hover/focus unless a column is actively sorted.
- Empty values render `—`, never `0`.

## 11. Controls and interaction

- Buttons are rectangular, 4px radius, sentence case.
- Segmented controls are connected and compact; active segment has a surface shift and brighter text, not a saturated fill.
- State chips alone may use pill geometry.
- Focus ring: `0 0 0 2px var(--bg-canvas), 0 0 0 3px var(--accent)`.
- Hover motion: 120ms color/border transition only. No scale, bounce, shimmer, or spring effects.
- New data may cross-fade over 160ms. Never animate the numeric value rolling upward.

## 12. Loading, stale, and failure states

- Loading: retain layout and use low-contrast skeleton blocks. No shimmer.
- Stale: always show exact age, then a plain-language consequence.
- Missing: render `No current observation` plus the expected source and last successful time.
- Attestation expired: keep the last values visible but add a full-width `EXPIRED` strip and disable policy freshness claims.
- Backend unavailable: keep the chosen lane unavailable and offer Demo as an explicit user choice; never substitute it automatically.
- Hash/chain failure: separate “evidence computed” from “evidence published.”

## 13. Responsive behavior

The demo is desktop-first at 1440px.

- ≥1280px: 12-column full layout.
- 900–1279px: chart 7 columns, comparison 5; diagnostic panels stack below.
- 640–899px: single column; KPI grid becomes 2×2; tables scroll horizontally.
- <640px: the asset rail moves above the main workspace, the KPI grid becomes 2×2, and bento cards stack.

Do not hide timestamps, evidence explanations, or policy provenance on smaller screens.

## 14. Accessibility and comprehension

- Minimum body contrast: WCAG AA.
- Never encode state by color alone.
- Every chart has a short text summary adjacent to it.
- Every technical metric gets one plain-English sentence.
- Use full labels before acronyms on first appearance.
- Keyboard order follows the evidence flow.
- Minimum interactive target: 36px desktop, 44px touch.

## 15. Voice and copy

Tone: precise, neutral, auditable.

Prefer:

- `Evidence state: CHALLENGED`
- `Reference is outside the expected range`
- `Unexplained by model`
- `No current observation`
- `Protocol rule returned RESTRICT_NEW_RISK`

Avoid:

- `AI says...`
- `Bad oracle`
- `Definitely mispriced`
- `Critical! Act now!`
- `Safe / unsafe asset`

## 16. Anti-AI guardrails

Do not use:

- Purple/blue gradients or gradient text.
- Glassmorphism, backdrop blur, glow, or bloom.
- Decorative charts, floating orbs, constellations, or grid backgrounds.
- Icons in every statistic tile.
- Large rounded cards with equal padding everywhere.
- Marketing hero sections inside the product.
- Generic “insights” cards with sparkle icons.
- Emoji.
- Excess badges.
- Invented metrics or copy that implies unavailable certainty.

## 17. Demo scenario

Ship the single backend-owned `weekend_divergence` sequence and its matching offline fixture. Six five-minute anchors progress through SUPPORTED, INCONCLUSIVE, and CHALLENGED over 25 minutes. The overview derives 26 one-minute presentation frames for smooth playback. This interpolation is demo-only and never applies to operational history.

## 18. Iterative build plan

### Iteration 1 — Skeleton and hierarchy (20–30 min)

- Implement app shell, asset rail, KPI row, central chart, and compact bento cards.
- Use only grayscale tokens.
- Acceptance check: a judge can answer “what is being assessed, what is the evidence state, and what did the protocol do?” in 10 seconds.

### Iteration 2 — Analytical core (60–90 min)

- Add uncertainty-band chart, reference comparison, and synchronized hover state.
- Add basis breakdown and market-quality evidence.
- Acceptance check: the same values and timestamps appear consistently everywhere.

### Iteration 3 — Auditability (30–45 min)

- Add reason-code disclosures, onchain provenance, stale/expired states, and copy actions.
- Add one-line explanations for technical metrics.
- Acceptance check: every verdict can be traced to inputs and every policy result to a configured rule.

### Iteration 4 — Demo hardening and polish (30–45 min)

- Harden the single deterministic scenario and its offline fixture path.
- Test 1440px and 1024px, keyboard focus, missing values, and backend fallback.
- Remove any half-built feature, decorative icon, unused color, or repeated label.
- Acceptance check: the complete CHALLENGED story runs without live dependencies in under 90 seconds.

## 19. Final acceptance checklist

- Evidence State and Policy Result are visually and semantically separate.
- The uncertainty band is more visually important than the candles.
- State colors never encode price direction.
- All numbers use tabular sans-serif styling.
- Every changing value includes a source and/or timestamp.
- “Unexplained by model” is never called “mispricing.”
- No unsupported or fictional assets are shown.
- No gradient, glow, glass, hero, decorative stat icons, or excessive rounding.
- The deterministic scenario's SUPPORTED → INCONCLUSIVE → CHALLENGED progression is internally consistent.
- The app still tells a coherent story if the backend is unavailable.

## 20. Agent implementation prompt

> Build Valtide as a compact production risk overview. Use Inter throughout, with tabular numbers and no monospaced type. Keep the near-black canvas, graphite surfaces, hairline borders, spring accents, and restrained rounding. Put the compact horizontal price range beside the valuation chart on wide screens, with policy below it. Stack these panels at narrower widths. Preserve the evidence record and on-chain provenance. Keep copy terse, Evidence State separate from Policy Action, and the calibrated interval as the chart hero. Never invent OHLC candles or operational observations.
