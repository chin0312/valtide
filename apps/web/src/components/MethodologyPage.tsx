import { MODEL_EVIDENCE_SUMMARY } from "../fixtures/prototypeData";
import { MarketingHeader } from "./Hero";
import { MarketingFooter } from "./LandingPage";

const readerLenses = [
  { label: "New to Valtide", title: "Start with the decision boundary", body: "Understand the observed xStock validation target, why the answer is a range, and why evidence is not an instruction to liquidate." },
  { label: "Curators and risk teams", title: "Focus on abstention and provenance", body: "Review freshness, quality gates, reason codes, source dependence, and the policy boundary before changing exposure." },
  { label: "Developers and integrators", title: "Preserve the result intact", body: "Consume the backend state, interval, timestamps, model identity, and attestation without reclassifying evidence in the client." },
  { label: "Researchers", title: "Interrogate the model and evaluation", body: "Inspect causal update order, calibration, reference profiles, baselines, exposed evaluation data, and known limitations." },
] as const;

const pipeline = [
  { number: "01", title: "Observe", body: "Collect a point-in-time market snapshot. Keep the observed xStock validation target, trusted underlying anchor, exact-time X-Perp evidence, market state, source times, and liquidity fields distinct." },
  { number: "02", title: "Estimate", body: "Advance the P1a-C state-space challenger and return a fair-value center with calibrated predictive bounds. The interval is part of the answer, not decoration." },
  { number: "03", title: "Validate", body: "Apply the declared reference profile, quality gates, asset-specific evidence rules, and reason codes. Weak or unresolved evidence must be allowed to abstain." },
  { number: "04", title: "Deliver", body: "Publish an authorized attestation. Curator-owned policy maps the Evidence State to an action; the consuming application decides how that action is enforced." },
] as const;

const states = [
  { name: "SUPPORTED", tone: "supported", body: "The active, validated rule finds no material reason to challenge the reference from the available evidence. It does not prove the reference correct." },
  { name: "INCONCLUSIVE", tone: "inconclusive", body: "Evidence is missing, stale, weak, dependent, uncalibrated, or near an unresolved boundary. Abstention is a deliberate result, not a system error." },
  { name: "CHALLENGED", tone: "challenged", body: "The active rule finds a material inconsistency with sufficiently strong corroborating evidence. It warrants review; it does not prove oracle fault." },
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
            <p>Valtide produces source-aware valuation evidence for an explicitly named validation target. The current production profile evaluates the observed xStock using a model-based P1a-C challenger and separately sourced X-Perp evidence while preserving uncertainty and the boundary between evidence and protocol policy.</p>
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
              <div><dt>Challenger</dt><dd>{MODEL_EVIDENCE_SUMMARY.model}</dd></div>
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
          <div className="methodology-heading"><span>03</span><div><p className="marketing-kicker">Framework</p><h2>Observe → estimate → validate → deliver.</h2><p>No source is silently averaged into an opaque consensus price. The disagreement and its provenance remain visible.</p></div></div>
          <div className="methodology-pipeline">{pipeline.map((step) => <article key={step.number}><span>{step.number}</span><h3>{step.title}</h3><p>{step.body}</p></article>)}</div>
        </section>

        <section className="methodology-section methodology-section--profiles">
          <div className="methodology-heading"><span>04</span><div><p className="marketing-kicker">Information set and source dependence</p><h2>A result only means what its reference profile permits.</h2><p>The profile names the price being evaluated and its relationship to the challenger inputs. Comparisons with shared inputs must not be described as independent votes.</p></div></div>
          <div className="profile-table" role="table" aria-label="Current reference profiles">
            <div className="profile-table__head" role="row"><span role="columnheader">Profile</span><span role="columnheader">What is compared</span><span role="columnheader">Interpretation</span></div>
            <div role="row"><strong role="cell">Production unified profile</strong><p role="cell">The observed xStock is the validation target. P1a-C has assimilated that same observation, while exact-time X-Perp is preserved as a separately sourced second-market challenger.</p><p role="cell">xStock-versus-P1a is model-based evidence, not two independent observations. Asset-bound tri-source capability determines whether support and challenge states are authorized.</p></div>
            <div role="row"><strong role="cell">Legacy persisted results</strong><p role="cell">Older records and fixtures may identify X-Perp as the reference under test under <code>legacy_xperp_vs_p1ac</code>.</p><p role="cell">These rows remain readable for provenance but are not the current operational classifier and must not be blended with v2 Evidence States.</p></div>
          </div>
          <div className="source-grid">
            <article><span>Observed token market</span><h3>Confirmed OKX OnchainOS xStock candles</h3><p>Canonical five-minute observations carry source identity, observation time, volume, and available liquidity metadata.</p></article>
            <article><span>Trusted underlying</span><h3>Point-in-time U.S. equity observations</h3><p>The configured underlying feed anchors and later updates model state. Current same-time underlying data is assimilated only after the challenger quote is emitted.</p></article>
            <article><span>Separate comparator</span><h3>OKX X-Perp index</h3><p>Preserved as a distinct market observation. It does not alter the P1a-C estimate, interval, or carried state.</p></article>
            <article><span>Excluded from the estimator</span><h3>No Pyth or constructed consensus input</h3><p>External constructed references may be displayed as diagnostics, but they cannot change the current numerical fair value or interval.</p></article>
          </div>
        </section>

        <section className="methodology-section methodology-section--model">
          <div className="methodology-heading"><span>05</span><div><p className="marketing-kicker">Implemented challenger</p><h2>P1a-C is a causal state-space estimate with calibrated uncertainty.</h2><p>Asset-specific P1a-C bundles are operational for NVDAx, SPYx, and AAPLx. The published interval study below describes the NVDAx artifact, which uses log prices, session-specific process variance, separate observation noise, and empirical session-aware calibration.</p></div></div>
          <div className="model-layout">
            <div className="equation-stack" aria-label="P1a-C calculation summary">
              <div><span>Predict uncertainty</span><code>P⁻ₜ = Pₜ₋₁ + Q(session)</code></div>
              <div><span>Assimilate xStock observation</span><code>Kₜ = P⁻ₜ / (P⁻ₜ + Rₓ)</code><code>mₜ = m⁻ₜ + Kₜ(log Tₜ − m⁻ₜ)</code></div>
              <div><span>Return challenger center</span><code>Fₜ = exp(mₜ)</code></div>
              <div><span>Return calibrated bounds</span><code>[Lₜ,Uₜ] = exp(mₜ + [qₗ,qᵤ] √(Pₜ + Rᵤ))</code></div>
            </div>
            <div className="causal-order">
              <p className="marketing-kicker">Causal update order</p>
              <ol><li>Predict the latent state.</li><li>Assimilate the current xStock observation.</li><li>Emit fair value and the P1a-C interval.</li><li>Only then assimilate the current underlying observation for the next timestamp.</li></ol>
              <p>This prevents a current underlying observation from leaking into the challenger quote used to evaluate it. It does not make xStock-versus-P1a independent, because xStock is an explicit model input.</p>
            </div>
          </div>
          <div className="calibration-strip"><div><span>Calibration family</span><strong>Session-symmetric</strong></div><div><span>Calibration scores</span><strong>22,441</strong></div><div><span>Training cutoff</span><strong>2026-06-23 14:15 UTC</strong></div><div><span>Closed / overnight</span><strong>Global fallback</strong></div></div>
        </section>

        <section className="methodology-section methodology-section--states">
          <div className="methodology-heading"><span>06</span><div><p className="marketing-kicker">Evidence State</p><h2>Quality gates can override an apparent price signal.</h2><p>The backend—not the browser—applies the active decision rule. Missing token data, stale sources, suspected unit errors, invalid or high uncertainty, unavailable comparators, and unverified calibration can force an abstention.</p></div></div>
          <div className="methodology-states">{states.map((state) => <article className={state.tone} key={state.name}><span>{state.name}</span><p>{state.body}</p></article>)}</div>
          <div className="methodology-rule"><span>CURRENT V2 RULE BOUNDARY</span><p>The unified profile begins at <strong>INCONCLUSIVE</strong>. It emits <strong>SUPPORTED</strong> when the asset-authorized support band applies, exact-time X-Perp is available, and quality gates pass. It emits <strong>CHALLENGED</strong> only when the authorized review-band rule applies and exact-time X-Perp is closer to P1a-C than to xStock. Watch-band, missing, stale, ambiguous, or quality-gated evidence remains <strong>INCONCLUSIVE</strong>. State authority comes from the asset-bound tri-source capability artifact, not the detector promotion label alone.</p></div>
        </section>

        <section className="methodology-section methodology-section--evaluation">
          <div className="methodology-heading"><span>07</span><div><p className="marketing-kicker">Evaluation evidence</p><h2>The published test evaluates interval quality—not production oracle accuracy.</h2><p>P1a-C and the Gaussian baseline use the same point estimates. The comparison isolates the construction of uncertainty ranges over the exposed June–September 2026 evaluation period.</p></div></div>
          <div className="evaluation-metrics">
            <article><span>TEST OBSERVATIONS</span><strong>{MODEL_EVIDENCE_SUMMARY.observations.toLocaleString("en-US")}</strong><p>Contemporaneous observations in the exposed test report.</p></article>
            <article><span>EMPIRICAL COVERAGE</span><strong>{(MODEL_EVIDENCE_SUMMARY.coverage * 100).toFixed(1)}%</strong><p>Benchmark observations captured against a {(MODEL_EVIDENCE_SUMMARY.coverageTarget * 100).toFixed(0)}% target.</p></article>
            <article><span>MEAN INTERVAL WIDTH</span><strong>{MODEL_EVIDENCE_SUMMARY.meanIntervalWidthBps.toFixed(2)} bps</strong><p>{widthReduction}% narrower than the conventional Gaussian interval using the same centers.</p></article>
            <article><span>POINT MAE</span><strong>{MODEL_EVIDENCE_SUMMARY.maeBps.toFixed(3)} bps</strong><p>Shared point-estimate error reported for this evaluation.</p></article>
          </div>
          <div className="evaluation-caveats"><strong>How to read these results</strong><ul><li>Coverage above target is not automatically better; width and interval score must be considered with it.</li><li>Closed and overnight intervals use a global calibration fallback because contemporaneous underlying labels are unavailable there.</li><li>The exposed test window is no longer an untouched lockbox and must not be reused for future model selection claims.</li><li>These interval results do not establish production performance, oracle-provider superiority, manipulation resistance, or Evidence State precision and recall.</li></ul></div>
          <div className="methodology-note"><strong>Separate v2 classification evidence</strong><p>The current support/challenge authority is bound per asset to a frozen detector and a 2026-09-21 through 2026-10-05 retrospective tri-source diagnostic. It supports a selective risk signal, not a prospective guarantee: NVDAx challenge candidates produced 5 true and 1 false positive among six truth-evaluable cases; SPYx produced 20 true and 0 false positives among 20; AAPLx had only four truth-labelled exact-time candidates, all tail events. Small samples and low recall remain explicit limitations.</p></div>
        </section>

        <section className="methodology-section methodology-section--audit">
          <div className="methodology-heading"><span>08</span><div><p className="marketing-kicker">Reproducibility and delivery</p><h2>Every conclusion carries identity and provenance.</h2><p>The human interface explains the result. The machine path carries the authorized attestation through the X Layer testnet control plane.</p></div></div>
          <div className="audit-layout">
            <ol><li><span>01</span><strong>P1a-C runtime</strong><small>Estimate, bounds, calibration metadata</small></li><li><span>02</span><strong>Backend validation</strong><small>Quality gates, Evidence State, reason codes</small></li><li><span>03</span><strong>ValidationRegistry</strong><small>Latest authorized attestation</small></li><li><span>04</span><strong>RiskGuard + consumer</strong><small>Curator policy and application enforcement</small></li></ol>
            <div><p className="marketing-kicker">Audit fields</p>{auditFields.map((field) => <span key={field}>{field}</span>)}</div>
          </div>
          <div className="methodology-links">
            <div><p className="marketing-kicker">Primary sources</p><h3>Inspect the method behind the page.</h3></div>
            <a href="https://github.com/chin0312/valtide/blob/main/docs/METHODOLOGY.md" target="_blank" rel="noreferrer">Research specification <span>↗</span></a>
            <a href="https://github.com/chin0312/valtide/tree/main/valtide-quant-service-p1ac/evidence" target="_blank" rel="noreferrer">Evaluation evidence <span>↗</span></a>
            <a href="https://github.com/chin0312/valtide/tree/main/valtide-quant-service-p1ac/artifacts" target="_blank" rel="noreferrer">Model artifacts <span>↗</span></a>
            <a href="/docs?profile=developers#role-guide">Integration guide <span>→</span></a>
          </div>
        </section>

        <section className="methodology-closing"><div><p className="marketing-kicker">Current limitation</p><h2>Credibility includes knowing when not to decide.</h2></div><p>Valtide is a research prototype on X Layer testnet. Its contracts are not audited production lending infrastructure. The browser is read-only, and <code>evidenceHash</code> is a commitment to canonical offchain evidence—not proof that the evidence is objectively correct.</p></section>
      </main>
      <MarketingFooter />
    </div>
  );
}
