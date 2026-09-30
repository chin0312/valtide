import { Hero } from "./Hero";

const DEMO = {
  observedAt: "2026-09-19 14:25 UTC",
  reference: "$180.00",
  token: "$178.20",
  fair: "$179.11",
  interval: "$178.81–$179.41",
  deviation: "+0.49%",
  standardized: "3.96σ",
} as const;

const storySteps = [
  { number: "01", label: "Observe", title: "A reference separates from the market evidence.", body: "Valtide keeps the reference under test, tokenized-market price, trusted anchor, market state, and timestamps visibly separate." },
  { number: "02", label: "Estimate", title: "Uncertainty remains part of the answer.", body: "The independent challenger produces a fair-value estimate with calibrated interval bounds—not a single price presented as truth." },
  { number: "03", label: "Validate", title: "Disagreement becomes an explainable Evidence State.", body: "The backend returns SUPPORTED, INCONCLUSIVE, or CHALLENGED together with reason codes and model provenance." },
  { number: "04", label: "Respond", title: "The protocol keeps control of policy.", body: "A curator-owned mapping turns evidence into a Policy Action. The consuming application decides how that action is enforced." },
] as const;

export function LandingPage() {
  return (
    <div className="marketing-shell">
      <Hero />
      <main>
        <section id="incident" className="story-section story-section--incident">
          <div className="section-index"><span>01</span><span>DETERMINISTIC DEMO</span></div>
          <div className="story-heading">
            <p className="marketing-kicker">One incident, fully traced</p>
            <h2>A reference is only useful while the evidence can support it.</h2>
            <p>This replay uses Valtide’s canonical six-observation <code>weekend_divergence</code> demo scenario. It is deterministic demonstration data—not live, operational, or historical performance evidence.</p>
          </div>

          <div className="incident-frame" aria-label="Canonical Valtide demo scenario">
            <div className="incident-topline">
              <span>NVDAx · MARKET CLOSED</span>
              <span>{DEMO.observedAt}</span>
              <span>MODEL P1a-C · 0.2.0</span>
            </div>
            <div className="incident-grid">
              <div className="incident-question">
                <span className="marketing-kicker">Reference under test</span>
                <strong>{DEMO.reference}</strong>
                <p>OKX X-Perp NVDA index</p>
              </div>
              <div className="incident-chart" aria-hidden="true">
                <div className="incident-band"><span>Valtide interval</span></div>
                <div className="incident-marker incident-marker--reference"><i />Reference {DEMO.reference}</div>
                <div className="incident-marker incident-marker--fair"><i />Fair value {DEMO.fair}</div>
                <div className="incident-marker incident-marker--token"><i />Token {DEMO.token}</div>
              </div>
              <div className="incident-result">
                <span className="marketing-kicker">Evidence State</span>
                <strong>CHALLENGED</strong>
                <p>Reference outside interval<br />Token and challenger agree</p>
              </div>
            </div>
            <div className="incident-metrics">
              <div><span>Valtide fair value</span><strong>{DEMO.fair}</strong></div>
              <div><span>90% target interval</span><strong>{DEMO.interval}</strong></div>
              <div><span>Reference deviation</span><strong>{DEMO.deviation}</strong></div>
              <div><span>Standardized deviation</span><strong>{DEMO.standardized}</strong></div>
            </div>
            <div className="incident-timeline" aria-label="Demo evidence progression">
              <span className="is-supported">14:00 · SUPPORTED</span>
              <span className="is-supported">14:05</span>
              <span className="is-supported">14:10</span>
              <span className="is-inconclusive">14:15 · INCONCLUSIVE</span>
              <span className="is-challenged">14:20</span>
              <span className="is-challenged">14:25 · CHALLENGED</span>
            </div>
          </div>
        </section>

        <section id="method" className="story-section">
          <div className="section-index"><span>02</span><span>THE REASONING CHAIN</span></div>
          <div className="story-heading story-heading--split">
            <h2>Not another price.<br />A test of the price already in use.</h2>
            <p>Valtide preserves the disagreement rather than averaging every source into one opaque number. The reference under test remains outside the independent challenger feature set.</p>
          </div>
          <div className="reasoning-grid">
            {storySteps.map((step) => <article key={step.number}>
              <div><span>{step.number}</span><span>{step.label}</span></div>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </article>)}
          </div>
        </section>

        <section className="story-section story-section--interval">
          <div className="section-index"><span>03</span><span>UNCERTAINTY</span></div>
          <div className="interval-copy">
            <p className="marketing-kicker">A range, not false precision</p>
            <h2>Valtide does not claim to observe an exact “true” price.</h2>
            <p>The challenger estimate is paired with calibrated interval bounds. A reference can be inside the expected range, near a boundary, or materially outside it; evidence quality and comparator availability still matter.</p>
            <a className="text-link" href="/docs#methodology">Read the methodology <span aria-hidden="true">↗</span></a>
          </div>
          <div className="range-instrument" aria-label="Illustrative interval based on the deterministic demo scenario">
            <div className="range-scale"><span>$178.00</span><span>$179.00</span><span>$180.00</span></div>
            <div className="range-track">
              <div className="range-band"><span>90% target interval</span></div>
              <i className="range-point range-point--token"><span>Token<br />$178.20</span></i>
              <i className="range-point range-point--fair"><span>Valtide<br />$179.11</span></i>
              <i className="range-point range-point--reference"><span>Reference<br />$180.00</span></i>
            </div>
            <p>Canonical demo observation · 2026-09-19 14:25 UTC · values rounded for display</p>
          </div>
        </section>

        <section className="story-section story-section--ownership">
          <div className="section-index"><span>04</span><span>OWNERSHIP BOUNDARY</span></div>
          <div className="story-heading">
            <p className="marketing-kicker">Evidence is not policy</p>
            <h2>Valtide says what the evidence supports. It does not prescribe one universal response.</h2>
          </div>
          <div className="ownership-flow">
            <article>
              <span>VALTIDE BACKEND</span>
              <strong>Evidence State</strong>
              <div className="state-list"><i>SUPPORTED</i><i>INCONCLUSIVE</i><i>CHALLENGED</i></div>
            </article>
            <b aria-hidden="true">→</b>
            <article>
              <span>CURATOR / PROTOCOL</span>
              <strong>Policy mapping</strong>
              <div className="policy-list"><i>ALLOW</i><i>MONITOR</i><i>REQUIRE_REVIEW</i><i>RESTRICT_NEW_RISK</i></div>
            </article>
            <b aria-hidden="true">→</b>
            <article>
              <span>CONSUMER</span>
              <strong>Enforcement</strong>
              <p>The consuming application defines what the returned action does.</p>
            </article>
          </div>
          <p className="ownership-note">The browser is read-only: it observes and explains. It does not calculate Evidence State, edit policy, hold the publisher signer, or publish attestations.</p>
        </section>

        <section className="story-section story-section--trail">
          <div className="section-index"><span>05</span><span>AUDITABLE DELIVERY</span></div>
          <div className="story-heading story-heading--split">
            <h2>Every conclusion leaves a trail.</h2>
            <p>The human interface explains the evidence. The machine interface carries an authorized attestation through the deployed X Layer testnet control plane.</p>
          </div>
          <div className="trail-flow">
            <div><span>01</span><strong>Operational validation</strong><small>Offchain model and validation engine</small></div>
            <div><span>02</span><strong>ValidationRegistry</strong><small>Latest authorized attestation</small></div>
            <div><span>03</span><strong>RiskGuard</strong><small>Curator-owned policy evaluation</small></div>
            <div><span>04</span><strong>Consumer</strong><small>Application-defined enforcement</small></div>
          </div>
          <div className="trail-fields">
            {['Observed at','Model / version','Interval bounds','Evidence State','Reason codes','Evidence hash','Valid until','Transaction / block'].map((field) => <span key={field}>{field}</span>)}
          </div>
          <p className="trail-disclaimer"><code>evidenceHash</code> is a provenance commitment to canonical offchain evidence. It is not proof that the evidence is objectively correct.</p>
        </section>

        <section className="story-section story-section--scope">
          <div className="scope-status">
            <span className="marketing-kicker">Current prototype scope</span>
            <dl>
              <div><dt>Available asset</dt><dd>NVDAx</dd></div>
              <div><dt>Reference under test</dt><dd>OKX X-Perp NVDA index</dd></div>
              <div><dt>Network</dt><dd>X Layer testnet · Chain ID 1952</dd></div>
              <div><dt>Evidence contexts</dt><dd>Operational · Historical · Demo</dd></div>
              <div><dt>Status</dt><dd>Research / hackathon prototype</dd></div>
            </dl>
          </div>
          <div className="scope-boundary">
            <span className="marketing-kicker">Deliberate boundaries</span>
            <h2>Not a replacement oracle. Not a lending protocol. Not an automatic liquidation engine.</h2>
            <p>The current contracts are testnet-only and are not audited production lending infrastructure. The DemoCollateralVault is a minimal reference consumer and does not custody assets, lend, trade, calculate LTV, or liquidate.</p>
          </div>
        </section>

        <section className="story-section story-section--docs">
          <div>
            <span className="marketing-kicker">Documentation</span>
            <h2>Understand the evidence before acting on it.</h2>
          </div>
          <div className="docs-bridges">
            <a href="/docs#read-result"><span>01</span><strong>Read a validation result</strong><small>Reference, interval, state, reasons, policy, and freshness.</small></a>
            <a href="/docs#curators"><span>02</span><strong>For curators and risk teams</strong><small>Investigate divergence and understand policy ownership.</small></a>
            <a href="/docs#developers"><span>03</span><strong>For developers</strong><small>API, Registry, RiskGuard, and attestation concepts.</small></a>
          </div>
          <div className="final-actions">
            <a className="primary-link" href="?view=console">Open validation console <span>↗</span></a>
            <a className="text-link" href="/docs">Explore documentation <span>→</span></a>
          </div>
        </section>
      </main>
      <MarketingFooter />
    </div>
  );
}

export function MarketingFooter() {
  return <footer className="marketing-footer">
    <a className="marketing-footer__brand" href="/"><span className="valtide-logo-crop"><img src="/valtide-logo.jpg" alt="" /></span>Valtide</a>
    <p>Independent collateral-valuation control for tokenized equities on X Layer.</p>
    <nav><a href="/docs">Docs</a><a href="/?view=console">Console</a><a href="https://github.com/chin0312/valtide" target="_blank" rel="noreferrer">GitHub ↗</a></nav>
  </footer>;
}
