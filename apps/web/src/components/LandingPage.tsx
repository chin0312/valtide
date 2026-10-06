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
  { number: "01", label: "Observe", title: "A reference separates from the market evidence.", body: "Valtide keeps the reference under test, tokenized-market price, trusted anchor, market state, and timestamps visibly separate." },
  { number: "02", label: "Estimate", title: "Uncertainty remains part of the answer.", body: "The independent challenger produces a fair-value estimate with calibrated interval bounds—not a single price presented as truth." },
  { number: "03", label: "Validate", title: "Disagreement becomes an explainable Evidence State.", body: "The backend returns SUPPORTED, INCONCLUSIVE, or CHALLENGED together with reason codes and model provenance." },
  { number: "04", label: "Respond", title: "The protocol keeps control of policy.", body: "A curator-owned mapping turns evidence into a Policy Action. The consuming application decides how that action is enforced." },
] as const;

const deliverySteps = [
  { number: "01", title: "Operational validation", body: "Offchain model and validation engine" },
  { number: "02", title: "ValidationRegistry", body: "Latest authorized attestation" },
  { number: "03", title: "RiskGuard", body: "Curator-owned policy evaluation" },
  { number: "04", title: "Consumer", body: "Application-defined enforcement" },
] as const;

const auditFields = ["Observed at", "Model / version", "Interval bounds", "Evidence State", "Reason codes", "Evidence hash", "Valid until", "Transaction / block"] as const;

const audienceGuides = [
  { label: "Read a result", title: "Understand a validation result", body: "Follow the reference, interval, Evidence State, reasons, policy, and freshness in the right order.", href: "/docs?profile=everyone#role-guide", action: "Open reader guide" },
  { label: "Risk teams", title: "Investigate and govern", body: "Separate evidence from policy, review divergence, and understand freshness before changing exposure.", href: "/docs?profile=curators#role-guide", action: "Open curator guide" },
  { label: "Developers", title: "Consume Valtide evidence", body: "Work with the API, ValidationRegistry, RiskGuard, and read-only attestation concepts.", href: "/docs?profile=developers#role-guide", action: "Open developer guide" },
] as const;

function GuideExplorer() {
  const [active, setActive] = useState(0);
  const selected = audienceGuides[active];
  return <div className="guide-explorer">
    <div className="guide-explorer__tabs" aria-label="Documentation by audience">
      {audienceGuides.map((guide, index) => <button type="button" key={guide.label} aria-pressed={active === index} onClick={() => setActive(index)}>{guide.label}</button>)}
    </div>
    <div className="guide-explorer__panel" aria-live="polite">
      <span>0{active + 1}</span>
      <div><h3>{selected.title}</h3><p>{selected.body}</p></div>
      <a href={selected.href}>{selected.action} <span aria-hidden="true">→</span></a>
    </div>
  </div>;
}

export function LandingPage() {
  const [demoFrame, setDemoFrame] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setDemoFrame((frame) => (frame + 1) % SCENARIO.length), 2200);
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
            <h2>A reference is only useful while the evidence can support it.</h2>
            <p>This six-step synthetic incident shows what happens as a collateral reference separates from independent market evidence. It is demonstration data—not live or historical performance.</p>
          </div>

          <div className="incident-frame" aria-label="Canonical Valtide demo scenario">
            <div className="incident-topline">
              <span>NVDAx · MARKET CLOSED</span>
              <span>{observedAt}</span>
              <span>SYNTHETIC INCIDENT · NOT LIVE</span>
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
              <div><span>Expected range · 90% coverage target</span><strong>{money(demo.fair_value_lower)}–{money(demo.fair_value_upper)}</strong></div>
              <div><span>Reference vs. estimate</span><strong>{signedPct(demo.reference_deviation_pct)}</strong></div>
            </div>
            <div className="incident-timeline" aria-label="Choose a demo observation">
              {SCENARIO.map((observation, index) => <button type="button" key={observation.timestamp} onClick={() => setDemoFrame(index)} aria-pressed={index === demoFrame} className={`is-${observation.evidence_state.toLowerCase()} ${index === demoFrame ? "is-active" : ""}`}>
                <strong>{observation.timestamp.slice(11, 16)}</strong>
                <em>{observation.evidence_state}</em>
              </button>)}
            </div>
            <p className="incident-instruction">Auto-playing the six observations. Select any time to inspect it immediately.</p>
          </div>
        </section>

        <section id="method" className="story-section story-section--reasoning">
          <div className="section-index"><span>02</span><span>THE REASONING CHAIN</span></div>
          <div className="story-heading story-heading--split">
            <h2>Not another price.<br />A test of the price already in use.</h2>
            <p>Valtide preserves the disagreement rather than averaging every source into one opaque number. The relationship depends on the reference profile: in the xStock profile P1a assimilates the same token observation, so the comparison is model-based challenger evidence—not two fully independent observations.</p>
          </div>
          <div className="reasoning-grid" aria-label="Valtide reasoning chain">
            {storySteps.map((step) => <article key={step.number}><div><span>{step.number}</span><span>{step.label}</span></div><h3>{step.title}</h3><p>{step.body}</p></article>)}
          </div>
        </section>

        <section className="story-section story-section--interval">
          <div className="section-index"><span>03</span><span>UNCERTAINTY</span></div>
          <div className="interval-copy">
            <p className="marketing-kicker">A range, not false precision</p>
            <h2>Valtide does not claim to observe an exact “true” price.</h2>
            <p>Valtide returns a range, not a supposedly exact price. The wider the uncertainty, the less confidently a protocol should rely on the estimate.</p>
            <a className="text-link" href="/methodology">Read the methodology <span aria-hidden="true">→</span></a>
          </div>
          <div className="range-instrument" aria-label="Illustrative interval based on the deterministic demo scenario">
            <div className="range-scale"><span>$178.00</span><span>$179.00</span><span>$180.00</span></div>
            <div className="range-track">
              <div className="range-band"><span>Expected range · 90% coverage target</span></div>
              <i className="range-point range-point--token"><span>Token<br />$178.20</span></i>
              <i className="range-point range-point--fair"><span>Valtide<br />$179.11</span></i>
              <i className="range-point range-point--reference"><span>Reference<br />$180.00</span></i>
            </div>
            <p>Canonical demo observation · 2026-09-19 14:25 UTC · values rounded for display</p>
          </div>
        </section>

        <section className="story-section story-section--ownership">
          <div className="section-index"><span>04</span><span>OWNERSHIP BOUNDARY</span></div>
          <div className="story-heading story-heading--ownership">
            <p className="marketing-kicker">Evidence is not policy</p>
            <h2>Valtide says what the evidence supports. It does not prescribe one universal response.</h2>
          </div>
          <div className="ownership-flow" aria-label="Evidence, policy, and enforcement ownership">
            <article><span>VALTIDE BACKEND</span><h3>Evidence State</h3><div><b>SUPPORTED</b><b>INCONCLUSIVE</b><b>CHALLENGED</b></div></article>
            <article><span>CURATOR / PROTOCOL</span><h3>Policy mapping</h3><div><b>ALLOW</b><b>MONITOR</b><b>REQUIRE_REVIEW</b><b>RESTRICT_NEW_RISK</b></div></article>
            <article><span>CONSUMER</span><h3>Enforcement</h3><p>The consuming application defines what the returned action does.</p></article>
          </div>
          <p className="ownership-note">The browser is read-only: it observes and explains. It does not calculate Evidence State, edit policy, hold the publisher signer, or publish attestations.</p>
        </section>

        <section className="story-section story-section--trail">
          <div className="section-index"><span>05</span><span>AUDITABLE DELIVERY</span></div>
          <div className="story-heading story-heading--split">
            <h2>Every conclusion leaves a trail.</h2>
            <p>The human interface explains the evidence. The machine interface carries an authorized attestation through the deployed X Layer testnet control plane.</p>
          </div>
          <div className="trail-flow" aria-label="Attestation delivery path">
            {deliverySteps.map((step) => <div key={step.number}><span>{step.number}</span><strong>{step.title}</strong><small>{step.body}</small></div>)}
          </div>
          <div className="trail-fields" aria-label="Fields carried through the audit trail">{auditFields.map((field) => <span key={field}>{field}</span>)}</div>
          <p className="trail-disclaimer"><code>evidenceHash</code> is a provenance commitment to canonical offchain evidence. It is not proof that the evidence is objectively correct.</p>
          <div className="prototype-scope">
            <div>
              <p className="marketing-kicker">Current prototype scope</p>
              <dl><div><dt>Available asset</dt><dd>NVDAx</dd></div><div><dt>Reference under test</dt><dd>OKX X-Perp NVDA index</dd></div><div><dt>Network</dt><dd>X Layer testnet · Chain ID 1952</dd></div><div><dt>Evidence contexts</dt><dd>Operational · Historical · Demo</dd></div><div><dt>Status</dt><dd>Research / hackathon prototype</dd></div></dl>
            </div>
            <div>
              <p className="marketing-kicker">Deliberate boundaries</p>
              <h3>Not a replacement oracle. Not a lending protocol. Not an automatic liquidation engine.</h3>
              <p>The current contracts are testnet-only and are not audited production lending infrastructure. The DemoCollateralVault is a minimal reference consumer and does not custody assets, lend, trade, calculate LTV, or liquidate.</p>
            </div>
          </div>
        </section>

        <section className="story-section story-section--docs">
          <div>
            <span className="marketing-kicker">Documentation</span>
            <h2>Understand the evidence before acting on it.</h2>
          </div>
          <GuideExplorer />
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
    <nav><a href="/methodology">Methodology</a><a href="/docs">Docs</a><a href="/?view=console">Console</a><a href="https://github.com/chin0312/valtide" target="_blank" rel="noreferrer">GitHub ↗</a></nav>
  </footer>;
}
