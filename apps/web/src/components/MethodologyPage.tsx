import { MODEL_EVIDENCE_SUMMARY } from "../fixtures/prototypeData";
import { MarketingHeader } from "./Hero";
import { MarketingFooter } from "./LandingPage";

const readerLenses = [
  { label: "New to Valtide", title: "Start with the decision boundary", body: "Understand Observed xStock, Valtide Fair Value, the Valuation Range, and why evidence is not an instruction to liquidate." },
  { label: "Curators and risk teams", title: "Focus on abstention and provenance", body: "Review freshness, quality gates, reason codes, source dependence, and the policy boundary before changing exposure." },
  { label: "Developers and integrators", title: "Preserve the result intact", body: "Consume the backend state, interval, timestamps, model identity, and attestation without reclassifying evidence in the client." },
  { label: "Researchers", title: "Interrogate the model and evaluation", body: "Inspect causal update order, calibration, reference profiles, baselines, exposed evaluation data, and known limitations." },
] as const;

const pipeline = [
  { number: "01", title: "Observe", body: "Collect a point-in-time market snapshot. Keep Observed xStock, the Underlying Anchor, separate X-Perp evidence, market status, source times, and liquidity fields distinct." },
  { number: "02", title: "Estimate", body: "The Valtide Model returns a Fair Value and Valuation Range. The range is part of the answer, not decoration." },
  { number: "03", title: "Validate", body: "Apply the declared reference profile, quality gates, asset-specific evidence rules, and reason codes. Weak or unresolved evidence must be allowed to abstain." },
  { number: "04", title: "Deliver", body: "Publish an authorized attestation. Curator-owned policy maps the Evidence State to an action; the consuming application decides how that action is enforced." },
] as const;

const states = [
  { name: "SUPPORTED", tone: "supported", condition: "Model Distance is within the asset’s supported range, exact-time X-Perp is available, and quality checks pass.", interpretation: "The observed price is consistent with the active evidence rule." },
  { name: "INCONCLUSIVE", tone: "inconclusive", condition: "Required evidence is missing, stale, ambiguous, or below quality requirements, or the evidence does not support a conclusive result.", interpretation: "Review the source data before using the price in a risk decision." },
  { name: "CHALLENGED", tone: "challenged", condition: "Model Distance is high and exact-time X-Perp is closer to Valtide Fair Value than to Observed xStock; quality checks pass.", interpretation: "Review the price before using it in a risk decision." },
] as const;

const auditFields = ["Observation and source timestamps", "Reference profile and instrument", "Model ID and version", "Interval and calibration source", "Evidence State and reason codes", "Evidence commitment and validity", "Transaction, block, and sequence"] as const;

export function MethodologyPage() {
  const widthReduction = (MODEL_EVIDENCE_SUMMARY.intervalWidthReduction * 100).toFixed(0);
  return (
    <div className="marketing-shell methodology-page">
      <MarketingHeader page />
      <main>
        <section className="methodology-hero">
          <div>
            <p className="marketing-kicker">Public research methodology · v0.3</p>
            <h1>How Valtide tests a price without pretending to know the “true” price.</h1>
            <p>Valtide compares Observed xStock with a model-based Valtide Fair Value and Valuation Range, alongside separately sourced X-Perp evidence. The xStock price is also a model input, while the Underlying Anchor provides context; neither is presented as an independent same-time vote. Evidence remains separate from protocol Policy Actions.</p>
            <div className="methodology-hero__actions">
              <a className="primary-link" href="/?view=console&context=demo">Inspect the demo <span aria-hidden="true">↗</span></a>
              <a className="text-link" href="https://github.com/chin0312/valtide/blob/main/docs/METHODOLOGY.md" target="_blank" rel="noreferrer">Read the research specification <span aria-hidden="true">↗</span></a>
            </div>
          </div>
          <aside aria-label="Methodology status">
            <span>METHOD STATUS</span>
            <dl>
              <div><dt>Operational validation</dt><dd>NVDAx · SPYx · AAPLx</dd></div>
              <div><dt>Onchain binding</dt><dd>NVDAx · SPYx · AAPLx</dd></div>
              <div><dt>Valtide Model</dt><dd>{MODEL_EVIDENCE_SUMMARY.model} · asset versions below</dd></div>
              <div><dt>Interval target</dt><dd>{(MODEL_EVIDENCE_SUMMARY.coverageTarget * 100).toFixed(0)}%</dd></div>
              <div><dt>Network</dt><dd>X Layer testnet</dd></div>
              <div><dt>Assurance</dt><dd>Research prototype</dd></div>
            </dl>
          </aside>
        </section>

        <section className="methodology-section methodology-section--boundary">
          <div className="methodology-heading"><span>01</span><div><p className="marketing-kicker">Scope and boundary</p><h2>A validation control—not a lending protocol.</h2></div></div>
          <div className="boundary-cards">
            <article><span>VALTIDE OWNS</span><h3>Evidence</h3><p>A challenger estimate, calibrated interval, Evidence State, reason codes, model identity, timestamps, and source provenance.</p></article>
            <article><span>CURATOR OWNS</span><h3>Policy</h3><p>The mapping from evidence to actions such as <code>ALLOW</code>, <code>MONITOR</code>, <code>REQUIRE_REVIEW</code>, or <code>RESTRICT_NEW_RISK</code>.</p></article>
            <article><span>CONSUMER OWNS</span><h3>Enforcement</h3><p>Collateral eligibility, haircuts, LTVs, margin calls, liquidation logic, and the application behaviour attached to each policy action.</p></article>
          </div>
          <div className="methodology-note"><strong>Deliberate non-claims</strong><p>Valtide does not observe an exact true price, replace the production oracle, prove manipulation, custody assets, calculate LTV, or automatically liquidate a position.</p></div>
        </section>

        <section className="methodology-section methodology-section--readers">
          <div className="methodology-heading"><span>02</span><div><p className="marketing-kicker">One method, four lenses</p><h2>The facts stay fixed. The reader’s questions change.</h2><p>The methodology is canonical across every audience. These lenses identify what each reader should scrutinize without changing equations, caveats, or claims.</p></div></div>
          <div className="methodology-lenses">{readerLenses.map((lens) => <article key={lens.label}><span>{lens.label}</span><h3>{lens.title}</h3><p>{lens.body}</p></article>)}</div>
        </section>

        <section className="methodology-section methodology-section--pipeline">
          <div className="methodology-heading"><span>03</span><div><p className="marketing-kicker">Framework</p><h2>Observe → estimate → validate → deliver.</h2><p>Disagreements are preserved, not averaged away. Each source, value, and timestamp remains visible alongside the result.</p></div></div>
          <div className="methodology-pipeline">{pipeline.map((step) => <article key={step.number}><span>{step.number}</span><h3>{step.title}</h3><p>{step.body}</p></article>)}</div>
        </section>

        <section className="methodology-section methodology-section--profiles">
          <div className="methodology-heading"><span>04</span><div><p className="marketing-kicker">Information set and source dependence</p><h2>A result only means what its reference profile permits.</h2><p>The profile identifies the price under review and each input’s role. The Valtide Model uses Observed xStock; exact-time X-Perp provides a separate market view.</p></div></div>
          <div className="profile-table" role="table" aria-label="Current reference profiles">
            <div className="profile-table__head" role="row"><span role="columnheader">Profile</span><span role="columnheader">What is compared</span><span role="columnheader">Interpretation</span></div>
            <div role="row"><strong role="cell">Current unified profile</strong><p role="cell">Observed xStock is the price under review and is also an input to Valtide Fair Value; exact-time X-Perp remains separate.</p><p role="cell">The price/model comparison is not independent market corroboration. Asset-specific authorization controls which Evidence States may be returned.</p></div>
            <div role="row"><strong role="cell">Legacy persisted results</strong><p role="cell">Older records and fixtures may identify X-Perp as the reference under test under <code>legacy_xperp_vs_p1ac</code>.</p><p role="cell">These rows remain readable for provenance but are not the current operational classifier and must not be blended with v2 Evidence States.</p></div>
          </div>
          <div className="source-grid">
            <article><span>Observed token market</span><h3>OKX OnchainOS xStock candle feed</h3><p>Canonical five-minute bars carry source identity, bar timing, volume, and available liquidity metadata; candle volume alone does not establish that every price change was an executed trade.</p></article>
            <article><span>Trusted underlying</span><h3>Point-in-time U.S. equity observations</h3><p>The configured underlying feed anchors and later updates model state. Current same-time underlying data is assimilated only after the challenger quote is emitted.</p></article>
            <article><span>Separate comparator</span><h3>OKX X-Perp index</h3><p>Preserved as a distinct market observation. It does not alter the Valtide Model estimate, Valuation Range, or carried state.</p></article>
            <article><span>Excluded from the estimator</span><h3>No Pyth or constructed consensus input</h3><p>External constructed references may be displayed as diagnostics, but they cannot change the current numerical fair value or interval.</p></article>
          </div>
        </section>

        <section className="methodology-section methodology-section--model">
          <div className="methodology-heading"><span>05</span><div><p className="marketing-kicker">Research implementation</p><h2>The Valtide Model estimates Fair Value with calibrated uncertainty.</h2><p>The deployed asset-specific artifacts use P1a-C: NVDAx v0.2.0 and SPYx/AAPLx v0.3.0. The historical interval study below is specifically the exposed NVDAx v0.2.0 artifact, which uses log prices, session-specific process variance, separate observation noise, and empirical session-aware calibration.</p></div></div>
          <div className="model-layout">
            <div className="causal-order">
              <p className="marketing-kicker">Causal update order</p>
              <ol><li>Predict the latent state.</li><li>Assimilate the available xStock observation.</li><li>Emit Valtide Fair Value and the Valuation Range.</li><li>Only then assimilate the current underlying observation for the next timestamp.</li></ol>
              <p>This ordering keeps same-time underlying data out of the estimate. Because xStock remains a model input, xStock-versus-model is model-based evidence; X-Perp is the separate market comparison.</p>
            </div>
            <details className="methodology-equations">
              <summary><span><small>Technical detail</small>View the P1a-C equations</span><span aria-hidden="true">＋</span></summary>
              <div className="equation-stack" aria-label="P1a-C calculation summary">
                <div><span>Predict uncertainty</span><code>P⁻ₜ = Pₜ₋₁ + Q(session)</code></div>
                <div><span>Assimilate xStock observation</span><code>Kₜ = P⁻ₜ / (P⁻ₜ + Rₓ)</code><code>mₜ = m⁻ₜ + Kₜ(log Tₜ − m⁻ₜ)</code></div>
                <div><span>Return Valtide Fair Value</span><code>Fₜ = exp(mₜ)</code></div>
                <div><span>Return calibrated bounds</span><code>[Lₜ,Uₜ] = exp(mₜ + [qₗ,qᵤ] √(Pₜ + Rᵤ))</code></div>
              </div>
              <a href="https://github.com/chin0312/valtide/blob/main/docs/METHODOLOGY.md" target="_blank" rel="noreferrer">Open the full research specification <span aria-hidden="true">↗</span></a>
            </details>
          </div>
          <div className="calibration-strip"><div><span>Calibration family</span><strong>Session-symmetric</strong></div><div><span>Calibration scores</span><strong>22,441</strong></div><div><span>Training cutoff</span><strong>2026-06-23 14:15 UTC</strong></div><div><span>Closed / overnight</span><strong>Global fallback</strong></div></div>
        </section>

        <section className="methodology-section methodology-section--states">
          <div className="methodology-heading"><span>06</span><div><p className="marketing-kicker">Evidence State</p><h2>Quality gates can override an apparent price signal.</h2><p>The backend—not the browser—applies the active decision rule. Missing token data, stale sources, suspected unit errors, invalid or high uncertainty, unavailable comparators, and unverified calibration can force an abstention.</p></div></div>
          <div className="state-rule-table" role="table" aria-label="Current unified Evidence State rules">
            <div className="state-rule-table__head" role="row"><span role="columnheader">Evidence State</span><span role="columnheader">Backend condition</span><span role="columnheader">Interpretation</span></div>
            {states.map((state) => <div className={state.tone} role="row" key={state.name}><strong role="cell">{state.name}</strong><p role="cell">{state.condition}</p><p role="cell">{state.interpretation}</p></div>)}
          </div>
          <div className="methodology-rule"><span>TECHNICAL RULE DETAIL</span><p>The frozen detector uses internal support, watch, and review bands. An asset-bound capability authorizes which Evidence States those detector outcomes may produce; band labels alone do not authorize a state.</p></div>
          <a className="methodology-inline-cta" href="/?view=console&context=demo">View these states in the Validation Console <span aria-hidden="true">→</span></a>
        </section>

        <section className="methodology-section methodology-section--evaluation">
          <div className="methodology-heading"><span>07</span><div><p className="marketing-kicker">Exposed NVDAx interval study · development evidence</p><h2>Interval quality—not production oracle accuracy.</h2><p>The June–September 2026 results describe NVDAx P1a-C v0.2.0 only. The model and Gaussian baseline use the same point estimates, isolating uncertainty-range construction; this is not a comparison against raw xStock, other assets, an oracle provider, or production performance.</p></div></div>
          <div className="evaluation-metrics">
            <article><span>NVDAx v0.2.0 · OBSERVATIONS</span><strong>{MODEL_EVIDENCE_SUMMARY.observations.toLocaleString("en-US")}</strong><p>Exposed historical/development interval-study observations.</p></article>
            <article><span>NVDAx · EMPIRICAL COVERAGE</span><strong>{(MODEL_EVIDENCE_SUMMARY.coverage * 100).toFixed(1)}%</strong><p>Benchmark observations captured against a {(MODEL_EVIDENCE_SUMMARY.coverageTarget * 100).toFixed(0)}% interval target.</p></article>
            <article><span>NVDAx · MEAN INTERVAL WIDTH</span><strong>{MODEL_EVIDENCE_SUMMARY.meanIntervalWidthBps.toFixed(2)} bps</strong><p>{widthReduction}% narrower than the Gaussian interval using the same centers.</p></article>
            <article><span>NVDAx · SHARED-CENTER POINT MAE</span><strong>{MODEL_EVIDENCE_SUMMARY.maeBps.toFixed(3)} bps</strong><p>Does not measure incremental accuracy over raw xStock.</p></article>
          </div>
          <div className="evaluation-interpretation"><strong>What the NVDAx interval results mean</strong><p>Narrower ranges are useful only when they retain adequate coverage. In this exposed study, NVDAx P1a-C v0.2.0 produced intervals {widthReduction}% narrower than the conventional Gaussian baseline while achieving {(MODEL_EVIDENCE_SUMMARY.coverage * 100).toFixed(1)}% empirical coverage against a {(MODEL_EVIDENCE_SUMMARY.coverageTarget * 100).toFixed(0)}% target. This is not evidence of lower point-price error than raw xStock.</p></div>
          <div className="evaluation-caveats"><strong>How to read these results</strong><ul><li>Coverage above target is not automatically better; width and interval score must be considered with it.</li><li>Closed and overnight intervals use a global calibration fallback because contemporaneous underlying labels are unavailable there.</li><li>The exposed June–September 2026 window is historical/development evidence, not an untouched lockbox, and must not be reused as confirmatory model-selection evidence.</li><li>These NVDAx interval results do not establish raw-xStock outperformance, three-asset performance, production performance, oracle-provider superiority, manipulation resistance, or Evidence State precision and recall.</li></ul></div>
          <div className="methodology-note"><strong>Separate v2 classification diagnostics</strong><p>The current support/challenge authority is bound per asset to a frozen detector and a retrospective tri-source diagnostic from 2026-09-21 through 2026-10-05. These are exploratory, selected truth-labelled candidates—not validated production precision or recall. NVDAx had 5 true and 1 false positive among six truth-evaluable candidates; SPYx had 20 true and 0 false positives among 20; AAPLx had only four truth-labelled exact-time candidates, all tail events. Samples are small, recall is limited, and future performance is untested.</p></div>
        </section>

        <section className="methodology-section methodology-section--audit">
          <div className="methodology-heading"><span>08</span><div><p className="marketing-kicker">Reproducibility and delivery</p><h2>Every conclusion carries identity and provenance.</h2><p>The human interface explains the result. The deployed X Layer testnet contracts show the attestation, policy-evaluation, and consumer boundary.</p></div></div>
          <div className="audit-layout">
            <ol><li><span>01</span><strong>P1a-C runtime</strong><small>Estimate, bounds, calibration metadata</small></li><li><span>02</span><strong>Backend validation</strong><small>Quality gates, Evidence State, reason codes</small></li><li><span>03</span><strong>ValidationRegistry</strong><small>Latest authorized compatible attestation</small></li><li><span>04</span><strong>RiskGuard + consumer</strong><small>Curator policy and application enforcement</small></li></ol>
            <div><p className="marketing-kicker">Audit fields</p>{auditFields.map((field) => <span key={field}>{field}</span>)}</div>
          </div>
          <div className="methodology-integration-note"><strong>Current testnet scope</strong><p>NVDAx, SPYx, and AAPLx have asset-specific publication bindings to the shared ValidationRegistry and RiskGuard on X Layer testnet. The backend scheduler publishes authorized attestations; the browser is read-only and does not submit or manually publish transactions. X Layer records evidence and evaluates policy—it does not calculate Fair Value.</p></div>
          <a className="methodology-inline-cta" href="/docs?profile=developers#role-guide">Explore the current X Layer testnet integration <span aria-hidden="true">→</span></a>
          <div className="methodology-links">
            <div><p className="marketing-kicker">Primary sources</p><h3>Inspect the method behind the page.</h3></div>
            <a href="https://github.com/chin0312/valtide/blob/main/docs/METHODOLOGY.md" target="_blank" rel="noreferrer">Research specification <span>↗</span></a>
            <a href="https://github.com/chin0312/valtide/tree/main/valtide-quant-service-p1ac/evidence" target="_blank" rel="noreferrer">Evaluation evidence <span>↗</span></a>
            <a href="https://github.com/chin0312/valtide/tree/main/valtide-quant-service-p1ac/artifacts" target="_blank" rel="noreferrer">Model artifacts <span>↗</span></a>
          </div>
        </section>

        <section className="methodology-closing"><div><p className="marketing-kicker">Current limitation</p><h2>Credibility includes knowing when not to decide.</h2></div><p>Valtide is a research prototype on X Layer testnet. Its contracts are not audited production lending infrastructure. The browser is read-only. <code>evidenceHash</code> records a commitment to canonical offchain evidence; correctness still depends on the underlying sources, model, and validation rule.</p></section>
      </main>
      <MarketingFooter />
    </div>
  );
}
