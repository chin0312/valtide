import { useEffect, useState } from "react";
import { MarketingFooter } from "./LandingPage";
import { MarketingHeader } from "./Hero";
import { documentationProfiles, type DocumentationProfileId } from "./documentationProfiles";

type VisualKind = "context" | "finding" | "boundary" | "triage" | "freshness" | "policy" | "payload" | "contracts" | "guard" | "signals" | "interval" | "evaluation";
type GuideId = DocumentationProfileId;

type Guide = {
  id: GuideId;
  label: string;
  eyebrow: string;
  title: string;
  summary: string;
  outcome: string;
  cta: string;
  href: string;
  walkthrough: readonly { eyebrow: string; title: string; body: string; tip: string; visual: VisualKind }[];
  checks: readonly [string, string][];
};

const guides: readonly Guide[] = [
  {
    id: "everyone", label: documentationProfiles.everyone.label, eyebrow: "A two-minute orientation", title: "Read the result without guessing what it means.",
    summary: "Start with the product language, then follow one result from its evidence context to the response configured by the curator.",
    outcome: "You will know what Valtide validates, what the three Evidence States mean, and where evidence stops and policy begins.",
    cta: "Open the demo result", href: "/?view=console&context=demo",
    walkthrough: [
      { eyebrow: "Begin with context", title: "Know what kind of evidence you are looking at.", body: "Operational, Historical, and Demo are different evidence lanes. The selected lane appears in the console header and is never silently substituted.", tip: "For your first visit, choose Demo. It contains six synthetic observations designed to explain the workflow.", visual: "context" },
      { eyebrow: "Read the finding", title: "Read the price, estimate, range, and state together.", body: "Compare Observed xStock with Valtide Fair Value and its Valuation Range, then inspect separately sourced X-Perp evidence. The Evidence State is the backend interpretation—not proof of a true price.", tip: "The Valtide Model uses the xStock observation as an input, so this comparison is not two independent market votes.", visual: "finding" },
      { eyebrow: "Keep the boundary clear", title: "Evidence describes. Policy decides.", body: "Valtide determines whether the evidence supports, cannot resolve, or challenges the observed xStock validation target. A curator maps that state to a Policy Action; the consuming application enforces it.", tip: "SUPPORTED does not automatically mean ALLOW, and CHALLENGED does not automatically mean liquidate.", visual: "boundary" },
    ],
    checks: [["SUPPORTED", "The observed price is consistent with the applicable model-distance rule, separately sourced X-Perp is available, and quality checks pass."], ["INCONCLUSIVE", "Evidence is missing, stale, ambiguous, or does not support a conclusive result."], ["CHALLENGED", "Model Distance is high and exact-time X-Perp supports the model-side comparison; quality checks pass."]],
  },
  {
    id: "curators", label: documentationProfiles.curators.label, eyebrow: "Investigation and governance", title: "Move from an evidence exception to a defensible response.",
    summary: "Triage the finding, verify freshness and provenance, then apply the response rules owned by your protocol.",
    outcome: "You will be able to investigate a challenged result without treating the model as a policy engine.",
    cta: "Inspect the policy view", href: "/?view=console",
    walkthrough: [
      { eyebrow: "Triage the exception", title: "Start with the reason for the challenge.", body: "Check Model Distance, the separately sourced X-Perp relationship, market status, quality checks, and structured Reason Codes before deciding whether an exception is actionable.", tip: "Reason Codes come from the backend. The browser displays them without reclassifying the result.", visual: "triage" },
      { eyebrow: "Verify the record", title: "Freshness and provenance come before policy.", body: "Confirm the observation timestamp, source timestamps, model version, attestation valid-until time, and your maximum accepted age.", tip: "A valid attestation can still be too old for a specific policy owner.", visual: "freshness" },
      { eyebrow: "Apply your response", title: "Map evidence through curator-owned policy.", body: "RiskGuard evaluates the current Evidence State and freshness against your configured mapping. The resulting action is a governance choice, not a model output.", tip: "Document why the mapping is appropriate for this collateral and revisit it as liquidity or market structure changes.", visual: "policy" },
    ],
    checks: [["Before escalation", "Confirm context, timestamp, market state, and source availability."], ["Before changing policy", "Separate a one-off data issue from a persistent evidence pattern."], ["Before enforcement", "Verify that the operational result and onchain attestation are synchronized."]],
  },
  {
    id: "developers", label: documentationProfiles.developers.label, eyebrow: "Integration path", title: "Consume evidence without moving the trust boundary.",
    summary: "Treat the API result and onchain attestation as authoritative inputs, preserve their provenance, let RiskGuard evaluate configured policy, and have the consuming application enforce the returned action.",
    outcome: "You will know which fields to consume, how publication reaches X Layer, and which checks belong in an integration.",
    cta: "Open the API reference", href: "https://valtide-api-production.up.railway.app/docs",
    walkthrough: [
      { eyebrow: "Consume the result", title: "Keep the response intact.", body: "Use the backend Evidence State, estimate, calibrated bounds, reason codes, timestamps, and source provenance. Do not recompute classification in the client.", tip: "Treat unknown reason codes as displayable structured data rather than as fatal parsing errors.", visual: "payload" },
      { eyebrow: "Follow publication", title: "Separate observation from delivery.", body: "The backend scheduler publishes authorized attestations to ValidationRegistry. Curator policy is stored separately, and RiskGuard evaluates both before the consumer acts.", tip: "The browser is read-only: it never signs or initiates a transaction or manual publication.", visual: "contracts" },
      { eyebrow: "Enforce safely", title: "Fail closed on stale or mismatched state.", body: "Check chain ID, contract addresses, asset identity, sequence, valid-until, policy maximum age, and current attestation before accepting a decision.", tip: "Do not pair cached operational evidence with a newer onchain policy state.", visual: "guard" },
    ],
    checks: [["Operational validation", "NVDAx, SPYx, and AAPLx have live schedulers, asset-specific runtimes, and canonical historical replay."], ["Current network", "A shared ValidationRegistry and RiskGuard are deployed on X Layer testnet with asset-specific bindings for NVDAx, SPYx, and AAPLx."], ["Current status", "Research prototype—not audited production lending infrastructure; QQQx remains offline research-only."]],
  },
  {
    id: "researchers", label: documentationProfiles.researchers.label, eyebrow: "Model and evaluation review", title: "Audit the challenger without overstating the evidence.",
    summary: "Inspect the point-in-time inputs, uncertainty construction, and evaluation design before drawing conclusions from coverage or interval width.",
    outcome: "You will understand what the challenger estimates, how its range is evaluated, and which claims the evidence cannot support.",
    cta: "Read the methodology", href: "/methodology",
    walkthrough: [
      { eyebrow: "Reconstruct the information set", title: "Keep every signal point-in-time correct.", body: "The current profile identifies Observed xStock as the price under review, the Valtide Model as an estimate that uses that observation, and exact-time X-Perp as a separately sourced market signal.", tip: "The xStock/model comparison is not independent; disagreement alone does not prove which price is correct.", visual: "signals" },
      { eyebrow: "Inspect uncertainty", title: "Evaluate the interval, not just its center.", body: "Valtide returns a fair-value estimate with a calibrated prediction interval. Wider ranges express greater uncertainty rather than false precision.", tip: "Coverage and interval width must be read together. Neither establishes point-price truth.", visual: "interval" },
      { eyebrow: "Read the evaluation", title: "Read the exposed interval study in context.", body: "The NVDAx P1a-C v0.2.0 historical/development study from June–September 2026 isolates interval construction: both methods use the same point estimates. It is not a comparison with raw xStock, other assets, an oracle provider, or a production track record.", tip: "The exposed interval contains 11,828 observations and targets 90% coverage; it is no longer an untouched test set.", visual: "evaluation" },
    ],
    checks: [["94.3% coverage", "NVDAx v0.2.0 empirical interval coverage in the exposed study at a 90% target."], ["19% narrower", "Mean NVDAx interval width versus a conventional Gaussian range using the same point estimates."], ["What is not claimed", "Raw-xStock outperformance, three-asset performance, Evidence State accuracy, production performance, or an observable exact true value."]],
  },
] as const;

const glossary = [
  { term: "Observed xStock", definition: "The tokenized-equity market price being reviewed. It is also an input to the current Valtide Model, so the comparison is not independent market evidence.", example: "At 14:25 UTC, the synthetic NVDAx Observed xStock price is $178.20." },
  { term: "Valtide Fair Value", definition: "The current model’s point estimate. It is a model output, not an objectively proven true price or a replacement oracle.", example: "$179.13 is the estimate’s center, not a guaranteed market price." },
  { term: "Valuation Range", definition: "The uncertainty range around Valtide Fair Value. Its target describes historical coverage, not a guarantee for an individual result.", example: "$178.83–$179.43 shows uncertainty around a $179.13 estimate." },
  { term: "Underlying Anchor", definition: "A trusted underlying-market observation used as model context and to update future state. It is not a same-time Evidence State vote.", example: "A prior regular-session NVDA observation can anchor the estimate while the equity market is closed." },
  { term: "X-Perp", definition: "A separately sourced market observation. It does not change the current estimate and is assessed with its own timestamp and availability.", example: "An exact-time X-Perp observation provides another market view; it does not prove which price is correct." },
  { term: "Model Distance", definition: "The measured disagreement between Observed xStock and Valtide Fair Value under the active asset rule.", example: "A high Model Distance may prompt review when source-quality checks also pass." },
  { term: "Evidence State", definition: "Valtide’s standardized interpretation of whether the observed xStock price is supported, inconclusive, or challenged under the active evidence rules.", example: "CHALLENGED prompts review; it does not prove xStock objectively wrong." },
  { term: "Policy Action", definition: "A response configured by the curator or consuming protocol. It is not generated by the quant model.", example: "A curator may map CHALLENGED to RESTRICT_NEW_RISK." },
  { term: "Attestation", definition: "The authorized onchain record of a validation observation stored by the ValidationRegistry.", example: "The record carries the observation time, evidence commitment, sequence, and validity window." },
  { term: "Freshness", definition: "Whether an attestation remains valid under both its valid-until time and the policy owner’s maximum age.", example: "An unexpired valid-until can still fail a curator’s stricter maximum-age rule." },
  { term: "Reason Codes", definition: "Structured backend explanations for an Evidence State, preserved by the frontend without recomputation.", example: "High Model Disagreement with X-Perp Supports Model Challenge can explain a CHALLENGED result." },
] as const;

const glossarySupplements: Record<GuideId, readonly { term: string; definition: string; example: string }[]> = {
  everyone: [
    { term: "Evidence context", definition: "The lane in which a result should be interpreted: Operational, Historical, or Demo.", example: "Demo contains synthetic observations for learning; it is not live evidence." },
    { term: "Trusted anchor", definition: "An external benchmark used as one independent input to the challenger model.", example: "It helps orient the estimate but does not become an unquestioned true price." },
    { term: "Market state", definition: "Whether the strongest reference market is open, closed, or otherwise constrained when the observation is made.", example: "A closed market can increase uncertainty and widen the prediction interval." },
  ],
  curators: [
    { term: "Maximum age", definition: "The policy owner’s limit on how old an attestation may be when it is used.", example: "A 15-minute limit can reject a still-unexpired attestation observed 16 minutes ago." },
    { term: "Stale evidence", definition: "An attestation that fails either its valid-until check or the applicable maximum-age rule.", example: "STALE is evaluated before a consumer relies on the configured state-to-action mapping." },
    { term: "Enforcement", definition: "The consuming application’s implementation of the Policy Action returned by its guard.", example: "RESTRICT_NEW_RISK might disable new borrowing while leaving repayment available." },
  ],
  developers: [
    { term: "Reference under test", definition: "A legacy compatibility field retained in API results and onchain identity. Older profile records may assign it a different semantic role from current Observed xStock validation.", example: "Read validation_target and xperp_role in current records instead of inferring meaning from this field name." },
    { term: "Evidence commitment", definition: "The cryptographic commitment that ties an attestation to its supporting evidence payload.", example: "Use it to verify that an API payload corresponds to the authorized onchain record." },
    { term: "Valid until", definition: "The timestamp after which the attestation is no longer valid, regardless of the Evidence State it contains.", example: "Check it again at decision time instead of relying on a cached frontend status." },
    { term: "Model provenance", definition: "The model version and associated metadata needed to identify how a result was produced.", example: "Preserve it with timestamps and source provenance when logging a decision." },
  ],
  researchers: [
    { term: "P1a-C challenger", definition: "The implemented NVDAx model version studied here estimates a center and uncertainty after assimilating the same xStock observation later compared with its output.", example: "Describe the difference as model-based evidence, not two independent observations or proof of a true price." },
    { term: "Calibration", definition: "The process of aligning an interval’s empirical coverage with its stated coverage target.", example: "A 90% target should be assessed using both observed coverage and interval width." },
    { term: "Point-in-time correctness", definition: "The requirement that every model input was genuinely available at the observation timestamp.", example: "Later revisions or future market data must not leak into a historical evaluation." },
  ],
};

function GuideVisual({ kind }: { kind: VisualKind }) {
  return <div className={`guide-shot guide-shot--${kind}`} role="img" aria-label={`${kind} product interface example`}>
    <div className="guide-shot__chrome"><i /><i /><i /><span>VALTIDE VALIDATION CONSOLE</span></div>
    {kind === "context" && <div className="shot-context"><p>EVIDENCE CONTEXT</p><div><b>Operational</b><b>Historical</b><b className="is-active">Demo</b></div><small>Demo scenario · 6 synthetic steps</small><span className="shot-callout">Choose the evidence lane here</span></div>}
    {kind === "finding" && <div className="shot-finding"><div><small>CURRENT FINDING · DEMO</small><strong>Observed xStock is supported</strong><p>Low Model Distance · X-Perp available · quality checks passed.</p></div><div className="shot-metrics"><span><small>OBSERVED XSTOCK</small><b>$180.00</b></span><span className="is-spotlit"><small>VALTIDE FAIR VALUE</small><b>$180.00</b><em>90% Valuation Range · $179.56–$180.44</em></span><span><small>EVIDENCE STATE</small><b className="is-supported">SUPPORTED</b></span></div><span className="shot-callout">Read price + range + state</span></div>}
    {kind === "boundary" && <div className="shot-boundary"><div><small>EVIDENCE</small><strong>SUPPORTED</strong><p>Price and quality checks pass</p></div><i>→</i><div className="is-spotlit"><small>CURATOR POLICY</small><strong>Allow new borrowing</strong><p>Configured mapping · ALLOW</p></div><i>→</i><div><small>CONSUMER</small><strong>Policy check passed</strong><p>Enforced by the application</p></div><span className="shot-callout">The middle decision belongs to the curator</span></div>}
    {kind === "triage" && <div className="shot-triage"><div><small>CURRENT FINDING</small><strong className="is-challenged">Observed xStock is challenged</strong><p>High Model Distance with X-Perp support</p></div><div className="shot-reasons is-spotlit"><small>WHY THIS STATE</small><b>High Model Disagreement</b><b>X-Perp Supports Model Challenge</b></div><span className="shot-callout">Start with structured reasons</span></div>}
    {kind === "freshness" && <div className="shot-freshness"><div className="is-spotlit"><small>ATTESTATION</small><strong>Sequence 184</strong><p>Observed 14:25 UTC</p><p>Valid until 14:40 UTC</p></div><div><small>POLICY LIMIT</small><strong>Maximum age</strong><p>15 minutes</p><b className="is-supported">FRESH</b></div><span className="shot-callout">Both clocks must pass</span></div>}
    {kind === "policy" && <div className="shot-policy"><div><small>EVIDENCE STATE</small><strong>SUPPORTED</strong><strong>INCONCLUSIVE</strong><strong>CHALLENGED</strong><strong>STALE</strong></div><div className="is-spotlit"><small>YOUR POLICY MAPPING</small><b>ALLOW</b><b>REQUIRE REVIEW</b><b>RESTRICT NEW RISK</b><b>REQUIRE REVIEW</b></div><span className="shot-callout">Curators own this mapping</span></div>}
    {kind === "payload" && <div className="shot-code is-spotlit"><code>{`{\n  "timestamp": "2026-09-19T14:00:00Z",\n  "token_price": 180.00,\n  "valtide_fair_value": 180.00,\n  "fair_value_lower": 179.56,\n  "fair_value_upper": 180.44,\n  "evidence_state": "SUPPORTED",\n  "reason_codes": ["P1A_XSTOCK_SUPPORT_BAND"],\n  "validation_target": "xstock_observed_price",\n  "evidence_semantics": "p1a_xstock_band_with_xperp_review_corroboration_v2",\n  "xperp_role": "second_market_challenger"\n}`}</code><span className="shot-callout">Consume; do not reclassify</span></div>}
    {kind === "contracts" && <div className="shot-contracts"><b>Publisher</b><i>→</i><b className="is-spotlit">ValidationRegistry<small>attestation</small></b><i>+</i><b>Curator Policy<small>mapping</small></b><i>→</i><b>RiskGuard<small>freshness + state</small></b><span className="shot-callout">Evidence and policy stay separate</span></div>}
    {kind === "guard" && <div className="shot-guard"><small>INTEGRATION CHECK</small><p><b>✓</b> Chain ID and contract match</p><p><b>✓</b> Asset and sequence match</p><p><b>✓</b> Attestation is within max age</p><p className="is-spotlit"><b>✓</b> Registry state read at decision time</p><span className="shot-callout">Check again at enforcement</span></div>}
    {kind === "signals" && <div className="shot-signals"><div><small>OBSERVED XSTOCK</small><strong>$178.20</strong><em>model input and price under review</em></div><div className="is-spotlit"><span><small>X-PERP</small><b>$180.00</b></span><span><small>UNDERLYING ANCHOR</small><b>$180.00</b></span><span><small>MARKET STATUS</small><b>CLOSED</b></span></div><span className="shot-callout">Preserve the information set</span></div>}
    {kind === "interval" && <div className="shot-interval"><small>90% VALUATION RANGE</small><div className="interval-axis"><i /><span className="interval-band">$178.83 – $179.43</span><b className="interval-fair">Valtide Fair Value<br />$179.13</b><b className="interval-ref">X-Perp<br />$180.00</b></div><span className="shot-callout">Read the range with its estimate</span></div>}
    {kind === "evaluation" && <div className="shot-evaluation"><span><small>NVDAx P1a-C v0.2.0 · JUNE–SEPT 2026 · EXPOSED</small><strong>11,828</strong></span><span className="is-spotlit"><small>INTERVAL COVERAGE</small><strong>94.3%</strong><em>90% target</em></span><span><small>MEAN INTERVAL WIDTH</small><strong>19% narrower</strong><em>vs Gaussian baseline</em></span><span className="shot-callout">Coverage is not point accuracy</span></div>}
  </div>;
}

export function DocsPage() {
  const [selectedRole, setSelectedRole] = useState(() => {
    if (typeof window === "undefined") return 0;
    const requestedProfile = new URLSearchParams(window.location.search).get("profile");
    const requestedIndex = guides.findIndex((candidate) => candidate.id === requestedProfile);
    return requestedIndex < 0 ? 0 : requestedIndex;
  });
  const guide = guides[selectedRole];
  const supplementaryTerms = glossarySupplements[guide.id];
  useEffect(() => {
    const targetId = window.location.hash.slice(1);
    if (!targetId) return;
    window.requestAnimationFrame(() => document.getElementById(targetId)?.scrollIntoView());
  }, []);
  return <div className="marketing-shell docs-page">
    <MarketingHeader page />
    <main>
      <section className="docs-hero"><div><p className="marketing-kicker">Valtide documentation</p><h1>One product. A guide for what you need to do.</h1><p>Choose the guide that matches your task: understand a result, investigate risk, integrate Valtide, or review the methodology.</p><div className="docs-hero__actions"><a className="primary-link" href="#start">Choose your guide ↓</a><a className="text-link" href="#glossary">Use the glossary →</a></div></div></section>
      <section id="start" className="docs-section docs-section--roles"><div className="docs-section__lead"><p className="marketing-kicker">Choose your profile</p><h2>What brings you to Valtide?</h2><p>Switch profiles at any time. The complete guide below updates with the concepts, tasks, and interface views most useful to that role.</p></div><div className="role-selector"><div className="role-selector__tabs" role="tablist" aria-label="Choose your Valtide role">{guides.map((role, index) => <button type="button" role="tab" id={`role-tab-${role.id}`} aria-controls="role-guide-panel" aria-selected={selectedRole === index} key={role.id} onClick={() => setSelectedRole(index)}><small>For</small>{role.label}</button>)}</div></div></section>
      <div id="role-guide-panel" className="role-guide" role="tabpanel" aria-labelledby={`role-tab-${guide.id}`} key={guide.id}>
        <section id="role-guide" className="docs-section role-guide__intro"><div><p className="marketing-kicker">{guide.eyebrow}</p><h2>{guide.title}</h2><p>{guide.summary}</p></div><aside><span>AFTER THIS GUIDE</span><p>{guide.outcome}</p></aside></section>
        <section className="docs-section docs-section--walkthrough"><div className="guide-walkthrough">{guide.walkthrough.map((item, index) => <article className="guide-walkthrough__row" key={item.title}><div className="guide-walkthrough__copy"><p className="marketing-kicker">{item.eyebrow}</p><h3>{item.title}</h3><p>{item.body}</p><div className="guide-tip"><span>KEEP IN MIND</span>{item.tip}</div></div><GuideVisual kind={item.visual} />{index < guide.walkthrough.length - 1 && <span className="guide-walkthrough__connector" aria-hidden="true">↓</span>}</article>)}</div></section>
        <section className="docs-section role-checks"><div className="docs-section__lead docs-section__lead--compact"><p className="marketing-kicker">Working reference</p><h2>{guide.id === "everyone" ? "Three states, with no hidden policy instruction." : "What to verify before you move on."}</h2></div><div className="role-checks__grid">{guide.checks.map(([label, copy]) => <article key={label}><span>{label}</span><p>{copy}</p></article>)}</div><a className="role-guide__cta" href={guide.href} target={guide.href.startsWith("http") ? "_blank" : undefined} rel={guide.href.startsWith("http") ? "noreferrer" : undefined}>{guide.cta} <span aria-hidden="true">↗</span></a></section>
      </div>
      <section id="glossary" className="docs-section docs-section--glossary"><div className="docs-section__lead docs-section__lead--compact"><p className="marketing-kicker">Shared vocabulary</p><h2>Use the product’s terms precisely.</h2><p>These definitions stay constant across every profile. Short examples show how each term appears in the current product.</p></div><dl className="glossary-grid">{glossary.map(({ term, definition, example }) => <div key={term}><dt>{term}</dt><dd>{definition}<small className="glossary-example"><span>EXAMPLE</span>{example}</small></dd></div>)}</dl><div className="role-glossary"><div className="role-glossary__heading"><p className="marketing-kicker">Also useful for</p><h3>{guide.label}</h3><p>These supporting concepts change with your selected profile, so the glossary stays focused on the decisions and questions you are most likely to encounter.</p></div><dl className="role-glossary__grid">{supplementaryTerms.map(({ term, definition, example }) => <div key={term}><dt>{term}</dt><dd>{definition}<small>{example}</small></dd></div>)}</dl></div></section>
        <section className="docs-section docs-section--scope"><div><p className="marketing-kicker">Current product scope</p><h2>A focused vertical slice.</h2><dl><div><dt>Operational validation</dt><dd>NVDAx / NVDA · SPYx / SPY · AAPLx / AAPL</dd></div><div><dt>Public asset selector</dt><dd>NVDAx, SPYx, AAPLx; each has a live scheduler, asset-specific runtime, and canonical historical panel.</dd></div><div><dt>Backend publication</dt><dd>The scheduler automatically publishes authorized attestations for configured assets; the browser remains read-only.</dd></div><div><dt>Research-only asset</dt><dd>QQQx retains offline quant and historical research but is not exposed through the public HTTP API.</dd></div><div><dt>Validation semantics</dt><dd>Observed xStock · Valtide Fair Value and Valuation Range · separate X-Perp evidence.</dd></div><div><dt>Onchain binding</dt><dd>NVDAx · SPYx · AAPLx · X Layer testnet</dd></div></dl></div><div><p className="marketing-kicker">Trust and limitations</p><h2>Research evidence, not a production guarantee.</h2><ul><li>No exact “true” fair value is observable while the strongest market is closed.</li><li>The exposed NVDAx interval study and retrospective diagnostics are not production guarantees.</li><li>The testnet contracts are not audited production lending infrastructure.</li><li>Valtide does not choose a universal LTV, trade, liquidate, or custody assets; consuming applications enforce their own policies.</li></ul></div></section>
    </main>
    <MarketingFooter />
  </div>;
}
