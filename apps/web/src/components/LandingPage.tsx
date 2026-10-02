import { useEffect, useState } from "react";
import type { ValuationResult } from "../api/types";
import weekendDivergence from "../fixtures/weekend_divergence.json";
import { Hero } from "./Hero";

const SCENARIO = weekendDivergence as unknown as ValuationResult[];
const REASON_LABELS: Record<string, string> = {
  REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL: "Reference outside interval",
  CALIBRATION_GLOBAL_FALLBACK: "Global fallback calibration",
  TOKEN_AND_CHALLENGER_AGREE: "Token and challenger agree",
};

function money(value: number | null) {
  return value === null ? "Unavailable" : `$${value.toFixed(2)}`;
}

function signedPct(value: number | null) {
  if (value === null) return "Unavailable";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function scaleTop(value: number | null) {
  if (value === null) return 50;
  return Math.max(12, Math.min(84, 18 + ((180 - value) / 2) * 64));
}

const storySteps = [
  { number: "01", label: "Observe", title: "The on-chain price drifts from the real stock.", body: "While the real market is closed, the token trades on thin pools and a stale reference. Valtide keeps the token price, the trusted anchor, and the reference under test side by side." },
  { number: "02", label: "Estimate", title: "We build a fair value — with a range, not false precision.", body: "An independent model estimates fair value and a calibrated interval around it, instead of one number presented as truth." },
  { number: "03", label: "Validate", title: "The gap becomes a clear verdict.", body: "The backend returns SUPPORTED, INCONCLUSIVE, or CHALLENGED, each with reason codes and model provenance you can replay." },
  { number: "04", label: "Respond", title: "The protocol decides what to do.", body: "A curator-owned rule turns the verdict into an action — from monitor up to blocking new borrowing. Valtide reports the state; the protocol owns the response." },
] as const;

export function LandingPage() {
  const [demoFrame, setDemoFrame] = useState(SCENARIO.length - 1);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setDemoFrame((frame) => (frame + 1) % SCENARIO.length), 1450);
    return () => window.clearInterval(timer);
  }, []);

  const demo = SCENARIO[demoFrame];
  const observedAt = `${demo.timestamp.slice(0, 10)} ${demo.timestamp.slice(11, 16)} UTC`;
  const intervalTop = scaleTop(demo.fair_value_upper);
  const intervalBottom = scaleTop(demo.fair_value_lower);

  return (
    <div className="marketing-shell">
      <Hero />
      <main>
        <section id="incident" className="story-section story-section--incident">
          <div className="section-index"><span>01</span><span>DETERMINISTIC DEMO</span></div>
          <div className="story-heading">
            <p className="marketing-kicker">One incident, fully traced</p>
            <h2>Watch a weekend price drift get caught.</h2>
            <p>This replay uses Valtide’s canonical six-observation <code>weekend_divergence</code> scenario. It is deterministic demo data — not live, operational, or historical performance evidence.</p>
          </div>

          <div className="incident-frame" aria-label="Canonical Valtide demo scenario">
            <div className="incident-topline">
              <span>NVDAx · MARKET CLOSED</span>
              <span className="incident-live"><i /> AUTO REPLAY · 5 MINUTE STEPS</span>
              <span>{observedAt}</span>
              <span>MODEL P1a-C · 0.2.0</span>
            </div>
            <div className="incident-grid">
              <div className="incident-question">
                <span className="marketing-kicker">Reference under test</span>
                <strong>{money(demo.reference_under_test)}</strong>
                <p>OKX X-Perp NVDA index</p>
              </div>
              <div className="incident-chart" aria-hidden="true">
                <div className="incident-band" style={{ top: `${intervalTop}%`, height: `${Math.max(4, intervalBottom - intervalTop)}%` }}><span>Valtide interval</span></div>
                <div className="incident-marker incident-marker--reference" style={{ top: `${scaleTop(demo.reference_under_test)}%` }}><i />Reference {money(demo.reference_under_test)}</div>
                <div className="incident-marker incident-marker--fair" style={{ top: `${scaleTop(demo.valtide_fair_value)}%` }}><i />Fair value {money(demo.valtide_fair_value)}</div>
                <div className="incident-marker incident-marker--token" style={{ top: `${scaleTop(demo.token_price)}%` }}><i />Token {money(demo.token_price)}</div>
              </div>
              <div className={`incident-result is-${demo.evidence_state.toLowerCase()}`}>
                <span className="marketing-kicker">Evidence State</span>
                <strong>{demo.evidence_state}</strong>
                <p>{demo.reason_codes.map((reason) => <span key={reason}>{REASON_LABELS[reason] ?? reason}</span>)}</p>
              </div>
            </div>
            <div className="incident-metrics">
              <div><span>Valtide fair value</span><strong>{money(demo.valtide_fair_value)}</strong></div>
              <div><span>90% target interval</span><strong>{money(demo.fair_value_lower)}–{money(demo.fair_value_upper)}</strong></div>
              <div><span>Reference deviation</span><strong>{signedPct(demo.reference_deviation_pct)}</strong></div>
              <div><span>Standardized deviation</span><strong>{demo.standardized_deviation === null ? "Unavailable" : `${demo.standardized_deviation.toFixed(2)}σ`}</strong></div>
            </div>
            <div className="incident-timeline" aria-label="Demo evidence progression">
              {SCENARIO.map((observation, index) => <span key={observation.timestamp} className={`is-${observation.evidence_state.toLowerCase()} ${index === demoFrame ? "is-active" : ""}`}>
                <strong>{observation.timestamp.slice(11, 16)}</strong>
                <em>{observation.evidence_state}</em>
              </span>)}
            </div>
          </div>
        </section>

        <section id="method" className="story-section">
          <div className="section-index"><span>02</span><span>THE REASONING CHAIN</span></div>
          <div className="story-heading story-heading--split">
            <h2>Not another price.<br />A test of the price already in use.</h2>
            <p>Valtide doesn't average every source into one opaque number. It keeps the disagreement, and checks the reference a protocol already relies on against an independent estimate.</p>
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
