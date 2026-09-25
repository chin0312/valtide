# Valtide Interface Design System

Status: extracted from the current frontend implementation

Last verified: 25 September 2026 against frontend commit `50f4d9b`

Audience: protocol risk teams, collateral curators, and technically curious judges  
Product posture: independent evidence and model validation for tokenized-equity collateral

Semantic authority: `../../docs/PRODUCT_SEMANTICS.md`. This document defines visual presentation only; data contexts, evidence, policy, freshness, and publication follow that contract.

Implementation sources: `src/index.css` for global tokens and typography; `src/App.tsx`, `src/components/`, and `src/views/` for the rendered hierarchy, component treatments, responsive behavior, and data visualizations. When this document and the application differ, the current implementation is the as-built source of truth.

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

The implemented palette is defined in `src/index.css`. Eight-digit hex values use the final two digits as alpha.

| Role | CSS token | Value |
|---|---|---|
| Canvas | `--color-bg` | `#050708` |
| Primary panel | `--color-panel` | `#0b0f10` |
| Raised / inset panel | `--color-panel-2` | `#111718` |
| Hover / tertiary panel | `--color-panel-3` | `#162022` |
| Subtle border | `--color-line-subtle` | `#182226` |
| Default border | `--color-line` | `#253237` |
| Strong border / axis | `--color-line-strong` | `#3b4d52` |
| Primary text | `--color-ink` | `#f3faf7` |
| Secondary text | `--color-ink-dim` | `#b8c7c2` |
| Muted text | `--color-muted` | `#71837d` |
| Interactive accent | `--color-accent` | `#affc41` |
| Accent hover | `--color-accent-hover` | `#b2ff9e` |
| Accent wash | `--color-accent-soft` | `#affc4117` |
| Token-market semantic alias | `--color-token` | `#1dd3b0` |
| Text selection | direct value | `#affc4138` |

### Evidence-state colors

| State | Foreground | Soft fill | Border |
|---|---|---|---|
| Supported | `--color-supported` · `#1dd3b0` | `--color-supported-soft` · `#1dd3b015` | `--color-supported-line` · `#1dd3b066` |
| Inconclusive | `--color-inconclusive` · `#affc41` | `--color-inconclusive-soft` · `#affc4115` | `--color-inconclusive-line` · `#affc4166` |
| Challenged | `--color-challenged` · `#d57ade` | `--color-challenged-soft` · `#3c164266` | `--color-challenged-line` · `#d57ade66` |

### Chart and source colors

| Source / layer | CSS token | Value |
|---|---|---|
| Reference under test | `--color-series-reference` | `#d8dee6` |
| Valtide fair value | `--color-series-valtide` | `#91b9ca` |
| Tokenized market | `--color-series-token` | `#1dd3b0` |
| Last trusted reference | `--color-series-trusted` | `#687786` |
| Valtide interval band | `--color-band-fill` | `#91b9ca1f` |

### Color rules

- Evidence states use a high-chroma spring trio: mint, acid-lime, and lifted plum. Never use traffic-light green/red.
- `#b2ff9e` is a hover/highlight tone, not a large background.
- Ordinary deltas are neutral gray with an explicit `+` or `−` sign.
- Never use green for “price went up” or red for “price went down.”
- Chart series use distinguishable neutral hues and line styles, not status colors.
- Never use gradients, glow, neon, or blurred color fields.
- Do not rely on color alone. Every state also gets text and a distinct marker shape.

## 5. Typography

### Font stack

- **Interface, headings, and labels:** `Inter`, then `Helvetica Neue`, Arial, and generic sans-serif.
- **Numbers, timestamps, hashes, codes, and axes:** the same Inter stack with tabular numerals.

Use one clean sans-serif family throughout. Tabular numerals keep live values aligned without a typewriter appearance. Two families is an upper limit, not a requirement.

```css
--font-sans: "Inter", "Helvetica Neue", Arial, sans-serif;
--font-mono: "Inter", "Helvetica Neue", Arial, sans-serif;
```

Inter is loaded from Google Fonts at weights 400, 500, and 600. The `font-mono` utility deliberately resolves to Inter: Valtide uses no visual monospace face. The `.tnum` class adds `font-variant-numeric: tabular-nums` for stable alignment. The body default is `14px / 1.5` at weight 400 with antialiasing.

### Type scale

| Role | Size / line | Weight | Tracking | Font |
|---|---:|---:|---:|---|
| Brand title | 22 / normal | 600 | -0.04em | UI |
| Evidence verdict | 24–30 / tight | 600 | -0.03em to -0.04em | UI |
| Featured figure | 25 / normal | 500 | -0.04em | Data |
| Primary metric | 20 / normal | 500 | -0.04em | Data |
| Secondary metric | 18 / tight | 500 | 0 | Data |
| Panel title | 15 / normal | 600 | -0.01em | UI |
| Body | 14 / 21 | 400 | 0 | UI |
| Body compact / control | 12 / normal | 400–500 | 0 | UI |
| Eyebrow / label | 10 / 14 | 500 | 0.10em | UI, uppercase |
| Caption / metadata | 9–11 / normal | 400–500 | 0–0.05em | UI or Data |

Rules:

- Use tabular numerals everywhere data can update.
- Keep headings at 600 maximum. Weight 700 appears only in the compact evidence marker, never in page hierarchy.
- Use tabular numerals for facts; no monospaced font.
- Currency symbols, unit suffixes, and insignificant decimals render at 60–70% visual emphasis—not a smaller hit target—and in `--text-muted`.
- Deltas sit inline with their value, smaller and neutral: `$190.00  +2.32%`.

### Iconography

- Icons are functional punctuation, never decoration.
- Use a 16px optical box, 1.5px stroke, subtly rounded outer corners, sharp internal joins, and square line terminals.
- Always pair unfamiliar icons with text. Prefer a text label when it is clearer than a symbol.
- Add small consistent outline icons to section headings and playback controls. Keep KPI tiles focused on numbers; all icons retain an adjacent text label.
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

- Desktop content max width: 1480px.
- Page gutters are 16px below the small breakpoint and 24px from 640px upward.
- The main analysis row is a single column until 1280px, then uses `1.3fr / 1fr` with a 16px gutter.
- Major section spacing is 16px in the implemented dashboard; internal content spacing uses the 4px base scale.
- Outer panel padding: 20px; compact cells and inset regions use 12–16px.
- Inputs and buttons: 32px compact, 36px default.
- KPI tiles form one connected grid with shared borders. No gaps and no floating-card shadows.
- Use `1px` borders. Never use more than one shadow level; default is none.

## 7. Information architecture

### Primary navigation and data source

Keep the current **Overview** layout with three explicit context controls: **Operational / Historical / Demo**. Operational is the default. Each context exposes its own truthful time-window controls and a Reset action.

- Operational uses warmed results and scheduler history. Missing data stays unavailable/degraded in this context; never auto-switch to Demo.
- Historical uses verified `historical_panel` replay and `source=historical` backtest metrics. Unavailability is explicit; scenario metrics never substitute.
- Demo is entered explicitly and uses only the six backend-owned scenario observations or their labelled offline fixture.
- Animate only the playhead between records. Metrics, timestamps, Evidence States, reasons, and record counts use the selected original observation in every context. Never construct synthetic `ValuationResult` objects.
- Prior operational and Historical observations show current-policy mappings, not historical on-chain decisions. X Layer remains explicitly current deployed state.

### Primary screen order

1. App bar and system freshness.
2. A searchable asset selector with NVDAx as the current asset and future assets clearly disabled as `Coming soon`.
3. Connected KPI strip.
4. Large valuation timeline beside a stack containing the horizontal price range and policy mapping at desktop widths.
5. Compact Evidence and Market Basis cards.
6. Evidence record with state distribution, transitions, and source facts.
7. Selected-observation audit and, in Historical context, model evidence.
8. X Layer provenance pipeline, including a legible read-only state when the API is unavailable.

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

NVDAx is the only selectable asset while it is the only asset supported by the backend. Future catalog entries may be discoverable, but must remain disabled and explicitly labelled `Coming soon`.

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
- Historical range control: `1H / 6H / 24H / 3D / 7D / ALL`; default `ALL`.
- Demo range control: `5M / 10M / 15M / FULL`; default `FULL`.
- Reset restores the context default, stops playback, and returns to the latest Operational/Historical observation or first Demo observation.
- Use real UTC spacing and break every series at scheduler gaps. Never interpolate missing observations.
- Demo playback retains exactly six five-minute observations; intermediate playhead positions are visual frames only, never evidence records.
- Do not render candlesticks until the backend exposes genuine OHLC inputs. The calibrated interval band is the truthful model-native visual.
- Legend supports click-to-isolate and keyboard focus.
- Tooltips show all sources at one timestamp and clearly mark stale/missing values.

### 9.5 Reference comparison

Use a single horizontal price axis.

All price-source markers share the axis centerline. Reference uses a white diamond, token market a mint circle, and last trusted a slate square. Source colors stay fixed across Evidence States. At equal prices, nest the outlined diamond and square around the smaller circle without shifting the price position. Keep values in the legend to avoid label collisions.

- One shaded Valtide range.
- Distinct source markers for reference under test, tokenized market, and last trusted value.
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
- Reference source lag and trusted-anchor age at the selected observation.
- Market-open status.

Render only supplied fields. Do not invent depth, spreads, volume windows, or frontend risk thresholds. Show the backend's five-minute USD volume when liquidity is unavailable, with its own label.

### 9.8 Reason codes

- Human-readable labels for exact backend reason codes, with the raw code available in a tooltip.
- State color appears only on the section's severity marker, not every chip.
- Show all returned reasons, including calibration diagnostics, or an explicit expandable count. Never infer why INCONCLUSIVE was returned from the state alone.

### 9.9 Onchain provenance

Use a linear verification strip:

`Publisher  →  Registry  →  Curator policy  →  RiskGuard  →  DemoVault`

Below it, show `evidenceHash`, transaction, block, issued-at, valid-until, and network in tabular text. Truncate hashes visually but make the full value copyable.

Only render fields supplied by the API. Expandable publication details retain auto-publish status, delivery status, last attempt, attempted and published observations, published time, full transaction hash, and errors, even if the chain read fails. Unavailable deployed policy is never labelled Demo mapping. An example policy is allowed only inside Demo and labelled not deployed.

The selected-observation audit exposes canonical UTC time, token/reference sources and observation times, reference source lag, trusted-anchor age, model/version, and source provenance. Current scheduler status/last attempt and current RiskGuard freshness are labelled separately from the selected record.

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
- Focus ring: `1px solid var(--color-accent)` with a `2px` outline offset.
- Hover motion: 120ms color/border transition only. No scale, bounce, shimmer, or spring effects.
- New data may cross-fade over 160ms. Never animate the numeric value rolling upward.

## 12. Loading, stale, and failure states

- Loading: retain layout and use low-contrast skeleton blocks. No shimmer.
- Observation age: show exact elapsed time neutrally. Source lags and trusted-anchor ages are backend values at the observation; do not infer a freshness verdict from them.
- Missing: render `No current observation` plus the expected source and last successful time.
- Attestation expired: keep the last values visible but add a full-width `EXPIRED` strip and disable policy freshness claims.
- Backend unavailable: keep the chosen lane unavailable and offer Demo as an explicit user choice; never substitute it automatically.
- Hash/chain failure: separate “evidence computed” from “evidence published.”

## 13. Responsive behavior

The demo is desktop-first at 1440px, with the following implemented Tailwind breakpoints:

- ≥1280px (`xl`): six-column KPI strip and `1.3fr / 1fr` chart-and-analysis layout.
- ≥768px (`md`): three-column KPI strip, two-column Evidence / Market Basis row, and five-stage provenance strip.
- ≥640px (`sm`): 24px page gutters and selected supporting grids expand where space permits.
- <640px: 16px page gutters, two-column KPI strip, and all major panels stack.

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

Ship the single backend-owned `weekend_divergence` sequence and its matching offline fixture. Six five-minute observations progress through SUPPORTED, INCONCLUSIVE, and CHALLENGED over 25 minutes. Smooth playhead animation never adds records or recomputes prices, timestamps, Evidence State, or reason codes. The evidence record always counts the six original observations.

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
