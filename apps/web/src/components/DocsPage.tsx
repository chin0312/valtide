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
      { eyebrow: "Read the finding", title: "Read the range and state together.", body: "Compare the reference under test with Valtide fair value and its calibrated range. Then use the Evidence State as the plain-language interpretation—not as proof of a true price.", tip: "A point estimate without its uncertainty range is incomplete.", visual: "finding" },
      { eyebrow: "Keep the boundary clear", title: "Evidence describes. Policy decides.", body: "Valtide determines whether the evidence supports, cannot resolve, or challenges the reference. A curator maps that state to a Policy Action; the consuming application enforces it.", tip: "SUPPORTED does not automatically mean ALLOW, and CHALLENGED does not automatically mean liquidate.", visual: "boundary" },
    ],
    checks: [["SUPPORTED", "No material reason to challenge the reference from the available evidence."], ["INCONCLUSIVE", "The evidence is too weak or inconsistent to make a strong call."], ["CHALLENGED", "The reference is materially inconsistent with sufficiently strong evidence; source dependence follows the named profile."]],
  },
  {
    id: "curators", label: documentationProfiles.curators.label, eyebrow: "Investigation and governance", title: "Move from an evidence exception to a defensible response.",
    summary: "Triage the finding, verify freshness and provenance, then apply the response rules owned by your protocol.",
    outcome: "You will be able to investigate a challenged result without treating the model as a policy engine.",
    cta: "Inspect the policy view", href: "/?view=console",
    walkthrough: [
      { eyebrow: "Triage the exception", title: "Start with the reason for the challenge.", body: "Check the deviation, model distance, market state, and structured reason codes before deciding whether an exception is actionable.", tip: "Reason codes come from the backend. The browser displays them without reclassifying the result.", visual: "triage" },
      { eyebrow: "Verify the record", title: "Freshness and provenance come before policy.", body: "Confirm the observation timestamp, source timestamps, model version, attestation valid-until time, and your maximum accepted age.", tip: "A valid attestation can still be too old for a specific policy owner.", visual: "freshness" },
      { eyebrow: "Apply your response", title: "Map evidence through curator-owned policy.", body: "RiskGuard evaluates the current Evidence State and freshness against your configured mapping. The resulting action is a governance choice, not a model output.", tip: "Document why the mapping is appropriate for this collateral and revisit it as liquidity or market structure changes.", visual: "policy" },
    ],
    checks: [["Before escalation", "Confirm context, timestamp, market state, and source availability."], ["Before changing policy", "Separate a one-off data issue from a persistent evidence pattern."], ["Before enforcement", "Verify that the operational result and onchain attestation are synchronized."]],
  },
  {
    id: "developers", label: documentationProfiles.developers.label, eyebrow: "Integration path", title: "Consume evidence without moving the trust boundary.",
    summary: "Treat the API result and onchain attestation as authoritative inputs, preserve their provenance, and let the deployed guard enforce configured policy.",
    outcome: "You will know which fields to consume, how publication reaches X Layer, and which checks belong in an integration.",
    cta: "Open the API reference", href: "https://valtide-api-production.up.railway.app/docs",
    walkthrough: [
      { eyebrow: "Consume the result", title: "Keep the response intact.", body: "Use the backend Evidence State, estimate, calibrated bounds, reason codes, timestamps, and source provenance. Do not recompute classification in the client.", tip: "Treat unknown reason codes as displayable structured data rather than as fatal parsing errors.", visual: "payload" },
      { eyebrow: "Follow publication", title: "Separate observation from delivery.", body: "The publisher writes an authorized attestation to ValidationRegistry. Curator policy is stored separately, and RiskGuard evaluates both before the consumer acts.", tip: "The browser is read-only: it never signs or initiates a transaction.", visual: "contracts" },
      { eyebrow: "Enforce safely", title: "Fail closed on stale or mismatched state.", body: "Check chain ID, contract addresses, asset identity, sequence, valid-until, policy maximum age, and current attestation before accepting a decision.", tip: "Do not pair cached operational evidence with a newer onchain policy state.", visual: "guard" },
    ],
    checks: [["Current asset", "NVDAx / NVDA is the only operational vertical slice; SPYx, QQQx, and AAPLx are catalog-visible but not operationally onboarded."], ["Current network", "ValidationRegistry and RiskGuard are deployed on X Layer testnet for NVDAx."], ["Current status", "Research prototype—not audited production lending infrastructure."]],
  },
  {
    id: "researchers", label: documentationProfiles.researchers.label, eyebrow: "Model and evaluation review", title: "Audit the challenger without overstating the evidence.",
    summary: "Inspect the point-in-time inputs, uncertainty construction, and evaluation design before drawing conclusions from coverage or interval width.",
    outcome: "You will understand what the challenger estimates, how its range is evaluated, and which claims the evidence cannot support.",
    cta: "Read the methodology", href: "https://github.com/chin0312/valtide/blob/main/docs/METHODOLOGY.md",
    walkthrough: [
      { eyebrow: "Reconstruct the information set", title: "Keep every signal point-in-time correct.", body: "The reference profile identifies the observed source and its relationship to model inputs. NVDAx's legacy X-Perp comparator is separate; the xStock profile compares the observed token with model-based challenger evidence after P1a has assimilated that same token observation.", tip: "The xStock and challenger values are not two fully independent observations; disagreement alone does not prove which price is correct.", visual: "signals" },
      { eyebrow: "Inspect uncertainty", title: "Evaluate the interval, not just its center.", body: "Valtide returns a fair-value estimate with a calibrated prediction interval. Wider ranges express greater uncertainty rather than false precision.", tip: "Coverage and interval width must be read together. Neither establishes point-price truth.", visual: "interval" },
      { eyebrow: "Read the evaluation", title: "Compare like with like.", body: "The historical test isolates uncertainty-range construction: both methods use the same point estimates. It is not a comparison with an oracle provider or a production track record.", tip: "The June–September 2026 test contains 11,828 observations and targets 90% coverage.", visual: "evaluation" },
    ],
    checks: [["94.3% coverage", "Share of contemporaneous trusted benchmarks captured at a 90% target."], ["19% narrower", "Mean interval width versus a conventional Gaussian range using the same point estimates."], ["What is not claimed", "Production performance, perfect independence, or an observable exact true value."]],
  },
] as const;

const glossary = [
      { term: "Reference under test", definition: "The explicitly identified price or valuation methodology Valtide evaluates. NVDAx uses the OKX X-Perp NVDA index as a separate reference; the xStock profile compares the observed token with model-based challenger evidence after P1a has assimilated that same token observation.", example: "In the legacy NVDAx profile, the reference is the $180.00 index value being evaluated." },
  { term: "Valtide fair value", definition: "The challenger model’s point estimate. For the xStock profile, the estimate has assimilated the same observed token price being compared, so the pair is not two fully independent observations. It is a model output, not an objectively proven true price.", example: "$179.11 is the challenger’s center estimate—not a replacement oracle price." },
  { term: "Prediction interval", definition: "The calibrated uncertainty range around the challenger estimate.", example: "$178.81–$179.41 expresses uncertainty around a $179.11 estimate at the selected coverage target." },
  { term: "Evidence State", definition: "Valtide’s standardized interpretation of whether the reference under test is supported, inconclusive, or challenged by available evidence.", example: "CHALLENGED means the reference is materially inconsistent with sufficiently strong evidence; it does not prove the reference wrong." },
  { term: "Policy Action", definition: "A response configured by the curator or consuming protocol. It is not generated by the quant model.", example: "A curator may map CHALLENGED to RESTRICT_NEW_RISK." },
  { term: "Attestation", definition: "The authorized onchain record of a validation observation stored by the ValidationRegistry.", example: "The record carries the observation time, evidence commitment, sequence, and validity window." },
  { term: "Freshness", definition: "Whether an attestation remains valid under both its valid-until time and the policy owner’s maximum age.", example: "An unexpired valid-until can still fail a curator’s stricter maximum-age rule." },
  { term: "Reason codes", definition: "Structured backend explanations for an Evidence State, preserved by the frontend without recomputation.", example: "REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL explains why a result was classified as CHALLENGED." },
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
    { term: "Evidence commitment", definition: "The cryptographic commitment that ties an attestation to its supporting evidence payload.", example: "Use it to verify that an API payload corresponds to the authorized onchain record." },
    { term: "Valid until", definition: "The timestamp after which the attestation is no longer valid, regardless of the Evidence State it contains.", example: "Check it again at decision time instead of relying on a cached frontend status." },
    { term: "Model provenance", definition: "The model version and associated metadata needed to identify how a result was produced.", example: "Preserve it with timestamps and source provenance when logging a decision." },
  ],
  researchers: [
    { term: "Challenger model", definition: "A model that estimates fair value and uncertainty. The legacy NVDAx X-Perp profile uses a separate reference; in the xStock profile, P1a assimilates the same token observation later compared with its output, so describe the result as model-based challenger evidence rather than two independent observations.", example: "Its output informs the Evidence State; it does not prove a true price or replace a reference." },
    { term: "Calibration", definition: "The process of aligning an interval’s empirical coverage with its stated coverage target.", example: "A 90% target should be assessed using both observed coverage and interval width." },
    { term: "Point-in-time correctness", definition: "The requirement that every model input was genuinely available at the observation timestamp.", example: "Later revisions or future market data must not leak into a historical evaluation." },
  ],
};

function GuideVisual({ kind }: { kind: VisualKind }) {
  return <div className={`guide-shot guide-shot--${kind}`} role="img" aria-label={`${kind} product interface example`}>
    <div className="guide-shot__chrome"><i /><i /><i /><span>VALTIDE VALIDATION CONSOLE</span></div>
    {kind === "context" && <div className="shot-context"><p>EVIDENCE CONTEXT</p><div><b>Operational</b><b>Historical</b><b className="is-active">Demo</b></div><small>Demo scenario · 6 synthetic steps</small><span className="shot-callout">Choose the evidence lane here</span></div>}
    {kind === "finding" && <div className="shot-finding"><div><small>CURRENT FINDING · DEMO</small><strong>Evidence supports the reference</strong><p>Available evidence does not materially challenge the price being tested.</p></div><div className="shot-metrics"><span><small>REFERENCE</small><b>$180.00</b></span><span className="is-spotlit"><small>VALTIDE FAIR VALUE</small><b>$180.00</b><em>$179.56–$180.44</em></span><span><small>EVIDENCE STATE</small><b className="is-supported">SUPPORTED</b></span></div><span className="shot-callout">Read center + range + state</span></div>}
    {kind === "boundary" && <div className="shot-boundary"><div><small>EVIDENCE</small><strong>SUPPORTED</strong><p>Token and challenger agree</p></div><i>→</i><div className="is-spotlit"><small>CURATOR POLICY</small><strong>Allow new borrowing</strong><p>Configured mapping · ALLOW</p></div><i>→</i><div><small>CONSUMER</small><strong>Policy check passed</strong><p>Enforced by the application</p></div><span className="shot-callout">The middle decision belongs to the curator</span></div>}
    {kind === "triage" && <div className="shot-triage"><div><small>CURRENT FINDING</small><strong className="is-challenged">Reference is challenged</strong><p>Outside the calibrated range by +4.0σ</p></div><div className="shot-reasons is-spotlit"><small>WHY THIS STATE</small><b>REFERENCE_OUTSIDE_INTERVAL</b><b>TOKEN_AND_CHALLENGER_DISAGREE</b></div><span className="shot-callout">Start with structured reasons</span></div>}
    {kind === "freshness" && <div className="shot-freshness"><div className="is-spotlit"><small>ATTESTATION</small><strong>Sequence 184</strong><p>Observed 14:25 UTC</p><p>Valid until 14:40 UTC</p></div><div><small>POLICY LIMIT</small><strong>Maximum age</strong><p>15 minutes</p><b className="is-supported">FRESH</b></div><span className="shot-callout">Both clocks must pass</span></div>}
    {kind === "policy" && <div className="shot-policy"><div><small>EVIDENCE STATE</small><strong>SUPPORTED</strong><strong>INCONCLUSIVE</strong><strong>CHALLENGED</strong><strong>STALE</strong></div><div className="is-spotlit"><small>YOUR POLICY MAPPING</small><b>ALLOW</b><b>REQUIRE REVIEW</b><b>RESTRICT NEW RISK</b><b>REQUIRE REVIEW</b></div><span className="shot-callout">Curators own this mapping</span></div>}
    {kind === "payload" && <div className="shot-code is-spotlit"><code>{`{\n  "evidence_state": "SUPPORTED",\n  "fair_value": 180.00,\n  "interval": [179.56, 180.44],\n  "reason_codes": ["TOKEN_AND_CHALLENGER_AGREE"],\n  "observed_at": "2026-09-19T14:00:00Z"\n}`}</code><span className="shot-callout">Consume; do not reclassify</span></div>}
    {kind === "contracts" && <div className="shot-contracts"><b>Publisher</b><i>→</i><b className="is-spotlit">ValidationRegistry<small>attestation</small></b><i>+</i><b>Curator Policy<small>mapping</small></b><i>→</i><b>RiskGuard<small>freshness + state</small></b><span className="shot-callout">Evidence and policy stay separate</span></div>}
    {kind === "guard" && <div className="shot-guard"><small>INTEGRATION CHECK</small><p><b>✓</b> Chain ID and contract match</p><p><b>✓</b> Asset and sequence match</p><p><b>✓</b> Attestation is within max age</p><p className="is-spotlit"><b>✓</b> Registry state read at decision time</p><span className="shot-callout">Check again at enforcement</span></div>}
    {kind === "signals" && <div className="shot-signals"><div><small>REFERENCE UNDER TEST</small><strong>$180.00</strong><em>excluded from inputs</em></div><div className="is-spotlit"><span><small>TOKEN MARKET</small><b>$178.20</b></span><span><small>TRUSTED ANCHOR</small><b>$180.00</b></span><span><small>MARKET STATE</small><b>CLOSED</b></span></div><span className="shot-callout">Preserve the information set</span></div>}
    {kind === "interval" && <div className="shot-interval"><small>90% CALIBRATED PREDICTION INTERVAL</small><div className="interval-axis"><i /><span className="interval-band">$178.66 – $179.56</span><b className="interval-fair">Fair value<br />$179.11</b><b className="interval-ref">Reference<br />$180.00</b></div><span className="shot-callout">Judge the range with the center</span></div>}
    {kind === "evaluation" && <div className="shot-evaluation"><span><small>OBSERVATIONS</small><strong>11,828</strong></span><span className="is-spotlit"><small>BENCHMARK COVERAGE</small><strong>94.3%</strong><em>90% target</em></span><span><small>MEAN RANGE WIDTH</small><strong>19% tighter</strong><em>vs Gaussian baseline</em></span><span className="shot-callout">Coverage is not point accuracy</span></div>}
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
        <section className="docs-section docs-section--scope"><div><p className="marketing-kicker">Current product scope</p><h2>A focused vertical slice.</h2><dl><div><dt>Current operational asset</dt><dd>NVDAx / NVDA</dd></div><div><dt>Asset selector</dt><dd>NVDAx, SPYx, QQQx, AAPLx; only NVDAx currently has a fitted runtime and deployed binding.</dd></div><div><dt>Other assets</dt><dd>SPYx · not operationally onboarded; verified model bundles and matching historical panels are still required.</dd></div><div><dt>Reference under test</dt><dd>NVDAx uses the OKX X-Perp index; other catalog profiles compare xStock with a challenger that has assimilated that same xStock input.</dd></div><div><dt>Network</dt><dd>X Layer testnet</dd></div></dl></div><div><p className="marketing-kicker">Trust and limitations</p><h2>Research evidence, not a production guarantee.</h2><ul><li>No exact “true” fair value is observable while the strongest market is closed.</li><li>Historical diagnostics are not production performance.</li><li>The testnet contracts are not audited production lending infrastructure.</li><li>Valtide does not choose a universal LTV, trade, liquidate, or custody assets.</li></ul></div></section>
    </main>
    <MarketingFooter />
  </div>;
}
