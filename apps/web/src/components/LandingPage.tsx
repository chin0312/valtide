import { useEffect, useState } from "react";
import type { ValuationResult } from "../api/types";
import weekendDivergence from "../fixtures/weekend_divergence.json";
import { documentationProfileList } from "./documentationProfiles";
import { Hero } from "./Hero";

const SCENARIO = weekendDivergence as unknown as ValuationResult[];
const REASON_LABELS: Record<string, string> = {
  CALIBRATION_GLOBAL_FALLBACK: "Global fallback calibration",
  TOKEN_AND_CHALLENGER_AGREE: "Token and challenger agree",
  P1A_XSTOCK_SUPPORT_BAND: "P1a/xStock support band",
  P1A_XSTOCK_WATCH_BAND: "P1a/xStock watch band",
  P1A_XSTOCK_REVIEW_BAND: "P1a/xStock review band",
  XPERP_CORROBORATES_P1A: "X-Perp corroborates P1a",
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
  { number: "01", label: "Observe", title: "An xStock price separates from its model-based challenger.", body: "Valtide keeps the observed xStock, P1a-C estimate, exact-time X-Perp evidence, trusted anchor, market state, and source timestamps visibly separate." },
  { number: "02", label: "Estimate", title: "Uncertainty remains part of the answer.", body: "P1a-C produces a fair-value estimate with calibrated interval bounds after assimilating the same xStock observation—not a fully independent vote or a single price presented as truth." },
  { number: "03", label: "Validate", title: "Tri-source evidence becomes an explainable state.", body: "Asset-specific support, watch, and review bands combine with exact-time X-Perp availability or directional corroboration to return SUPPORTED, INCONCLUSIVE, or CHALLENGED." },
  { number: "04", label: "Respond", title: "The protocol keeps control of policy.", body: "A curator-owned mapping turns evidence into a Policy Action. The consuming application decides how that action is enforced." },
] as const;

const deliverySteps = [
  { number: "01", title: "Operational validation", body: "Offchain model and validation engine" },
  { number: "02", title: "ValidationRegistry", body: "Latest authorized attestation" },
  { number: "03", title: "RiskGuard", body: "Curator-owned policy evaluation" },
  { number: "04", title: "Consumer", body: "Application-defined enforcement" },
] as const;

const auditFields = ["Observed at", "Model / version", "Interval bounds", "Evidence State", "Reason codes", "Evidence hash", "Valid until", "Transaction / block"] as const;

function GuideExplorer() {
  const [active, setActive] = useState(0);
  const selected = documentationProfileList[active];
  return <div className="guide-explorer role-selector">
    <div className="guide-explorer__tabs role-selector__tabs" role="tablist" aria-label="Documentation by audience">
      {documentationProfileList.map((guide, index) => <button type="button" role="tab" id={`landing-role-tab-${guide.id}`} aria-controls="landing-role-panel" key={guide.id} aria-selected={active === index} onClick={() => setActive(index)}><small>For</small>{guide.label}</button>)}
    </div>
    <div id="landing-role-panel" className="guide-explorer__panel" role="tabpanel" aria-labelledby={`landing-role-tab-${selected.id}`} aria-live="polite">
      <span>0{active + 1}</span>
      <div><h3>{selected.previewTitle}</h3><p>{selected.previewBody}</p></div>
      <a href={`/docs?profile=${selected.id}#role-guide`}>{selected.action} <span aria-hidden="true">→</span></a>
    </div>
  </div>;
}

export function LandingPage() {
  const [demoFrame, setDemoFrame] = useState(0);
  const [isDemoPlaying, setIsDemoPlaying] = useState(() => (
    typeof window === "undefined" || !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ));
  const [pauseReason, setPauseReason] = useState<"manual" | "focus" | null>(null);

  useEffect(() => {
    if (!isDemoPlaying) return;
    const timer = window.setInterval(() => setDemoFrame((frame) => (frame + 1) % SCENARIO.length), 4500);
    return () => window.clearInterval(timer);
  }, [isDemoPlaying]);

  function pauseDemo(reason: "manual" | "focus") {
    setIsDemoPlaying(false);
    setPauseReason(reason);
  }

  function toggleDemoPlayback() {
    setIsDemoPlaying((playing) => !playing);
    setPauseReason(null);
  }

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
            <h2>Watch a synthetic collateral reference diverge from market evidence.</h2>
            <p>This six-step synthetic incident shows what happens as the observed NVDAx price separates from its model-based challenger while exact-time X-Perp provides a second market view. It is demonstration data—not live or historical performance.</p>
          </div>

          <div className="incident-frame" aria-label="Canonical Valtide demo scenario">
            <div className="incident-topline">
              <span>NVDAx · MARKET CLOSED</span>
              <span>{observedAt}</span>
              <span>SYNTHETIC INCIDENT · NOT LIVE</span>
            </div>
            <div className="incident-grid">
              <div className="incident-question">
                <span className="marketing-kicker">Validation target</span>
                <strong>{money(demo.token_price)}</strong>
                <p>Observed NVDAx market price</p>
              </div>
              <div className="incident-chart" aria-hidden="true">
                <div className="incident-band" style={{ top: `${intervalTop}%`, height: `${Math.max(4, intervalBottom - intervalTop)}%` }}><span>Valtide interval</span></div>
                <div className="incident-marker incident-marker--reference" style={{ top: `${scaleTop(demo.xperp_index_price)}%` }}><i />X-Perp {money(demo.xperp_index_price)}</div>
                <div className="incident-marker incident-marker--fair" style={{ top: `${scaleTop(demo.valtide_fair_value)}%` }}><i />P1a-C {money(demo.valtide_fair_value)}</div>
                <div className="incident-marker incident-marker--token" style={{ top: `${scaleTop(demo.token_price)}%` }}><i />xStock {money(demo.token_price)}</div>
              </div>
              <div className={`incident-result is-${demo.evidence_state.toLowerCase()}`}>
                <span className="marketing-kicker">Evidence State</span>
                <strong>{demo.evidence_state}</strong>
                <p>{demo.reason_codes.map((reason) => <span key={reason}>{REASON_LABELS[reason] ?? reason}</span>)}</p>
              </div>
            </div>
            <div className="incident-metrics">
              <div><span>P1a-C fair value</span><strong>{money(demo.valtide_fair_value)}</strong></div>
              <div><span>Expected range · 90% coverage target</span><strong>{money(demo.fair_value_lower)}–{money(demo.fair_value_upper)}</strong></div>
              <div><span>xStock vs. P1a-C</span><strong>{signedPct(demo.xstock_vs_p1ac_deviation_pct)}</strong></div>
            </div>
            <div className="incident-timeline" aria-label="Choose a demo observation" onFocusCapture={() => pauseDemo("focus")}>
              {SCENARIO.map((observation, index) => <button type="button" key={observation.timestamp} onClick={() => { setDemoFrame(index); pauseDemo("manual"); }} aria-pressed={index === demoFrame} className={`is-${observation.evidence_state.toLowerCase()} ${index === demoFrame ? "is-active" : ""}`}>
                <strong>{observation.timestamp.slice(11, 16)}</strong>
                <em>{observation.evidence_state}</em>
              </button>)}
            </div>
            <div className="incident-playback" aria-live="polite">
              <p>{isDemoPlaying ? "Playing the six observations · 4.5 seconds per frame." : pauseReason === "manual" ? "Paused after manual selection." : pauseReason === "focus" ? "Paused while reviewing the timeline." : "Paused to respect your reduced-motion preference."}</p>
              <button type="button" onClick={toggleDemoPlayback} aria-pressed={isDemoPlaying} aria-label={`${isDemoPlaying ? "Pause" : "Play"} demo playback`}>
                <span aria-hidden="true">{isDemoPlaying ? "Ⅱ" : "▶"}</span>{isDemoPlaying ? "Pause" : "Play"}
              </button>
            </div>
          </div>
          <div className="incident-actions">
            <a className="text-link" href="/?view=console&context=demo">Inspect this synthetic incident in the Validation Console <span aria-hidden="true">↗</span></a>
          </div>
        </section>

        <section id="method" className="story-section story-section--reasoning">
          <div className="section-index"><span>02</span><span>THE REASONING CHAIN</span></div>
          <div className="story-heading story-heading--split">
            <h2>Test the price already in use with model-based challenger evidence.</h2>
            <p>Valtide preserves the disagreement rather than averaging every source into one opaque number. P1a assimilates the same xStock observation, so xStock-versus-P1a is model-based challenger evidence—not two fully independent observations. Exact-time X-Perp remains a separate second-market signal.</p>
          </div>
          <div className="reasoning-grid" aria-label="Valtide reasoning chain">
            {storySteps.map((step) => <article key={step.number}><div><span>{step.number}</span><span>{step.label}</span></div><h3>{step.title}</h3><p>{step.body}</p></article>)}
          </div>
        </section>

        <section className="story-section story-section--interval">
          <div className="section-index"><span>03</span><span>UNCERTAINTY</span></div>
          <div className="interval-copy">
            <p className="marketing-kicker">A range, not false precision</p>
            <h2>Calibrated ranges make uncertainty explicit.</h2>
            <p>Valtide returns a range, not a supposedly exact “true” price. The wider the uncertainty, the less confidently a protocol should rely on the estimate.</p>
            <a className="text-link" href="/methodology">Read the methodology <span aria-hidden="true">→</span></a>
          </div>
          <div className="range-instrument" aria-label="Illustrative interval based on the deterministic demo scenario">
            <div className="range-scale"><span>$178.00</span><span>$179.00</span><span>$180.00</span></div>
            <div className="range-track">
              <div className="range-band"><span>Expected range · 90% coverage target</span></div>
              <i className="range-point range-point--token"><span>Token<br />$178.20</span></i>
              <i className="range-point range-point--fair"><span>P1a-C<br />$179.13</span></i>
              <i className="range-point range-point--reference"><span>X-Perp<br />$180.00</span></i>
            </div>
            <p>Canonical demo observation · 2026-09-19 14:25 UTC · values rounded for display</p>
          </div>
        </section>

        <section className="story-section story-section--ownership">
          <div className="section-index"><span>04</span><span>OWNERSHIP BOUNDARY</span></div>
          <div className="story-heading story-heading--ownership">
            <p className="marketing-kicker">Evidence is not policy</p>
            <h2>Protocol-owned policy, evaluated on X Layer.</h2>
            <p>Valtide determines the Evidence State. RiskGuard evaluates the protocol’s configured mapping. The consuming application decides how—and whether—to enforce the returned action.</p>
          </div>
          <div className="ownership-flow" aria-label="Evidence, policy, and enforcement ownership">
            <article><span>VALTIDE BACKEND</span><h3>Evidence State</h3><div><b>SUPPORTED</b><b>INCONCLUSIVE</b><b>CHALLENGED</b></div></article>
            <article><span>CURATOR / PROTOCOL</span><h3>Policy mapping</h3><div><b>ALLOW</b><b>MONITOR</b><b>REQUIRE_REVIEW</b><b>RESTRICT_NEW_RISK</b></div></article>
            <article><span>CONSUMER</span><h3>Enforcement</h3><p>The consuming application defines what the returned action does.</p></article>
          </div>
          <p className="ownership-note">The browser is read-only: it observes and explains. It does not calculate Evidence State, edit policy, hold the publisher signer, sign, or submit transactions.</p>
        </section>

        <section className="story-section story-section--trail">
          <div className="section-index"><span>05</span><span>AUDITABLE DELIVERY</span></div>
          <div className="story-heading story-heading--split">
            <h2>Every conclusion leaves a trail.</h2>
            <p>The human interface explains the evidence. For NVDAx, SPYx, and AAPLx, the machine interface can publish authorized attestations to the deployed X Layer testnet control plane; consuming applications remain responsible for enforcement.</p>
          </div>
          <div className="trail-flow" aria-label="Attestation delivery path">
            {deliverySteps.map((step) => <div key={step.number}><span>{step.number}</span><strong>{step.title}</strong><small>{step.body}</small></div>)}
          </div>
          <div className="trail-fields" aria-label="Fields carried through the audit trail">{auditFields.map((field) => <span key={field}>{field}</span>)}</div>
          <p className="trail-disclaimer"><code>evidenceHash</code> is a provenance commitment to canonical offchain evidence. It is not proof that the evidence is objectively correct.</p>
          <div className="prototype-scope">
            <div>
              <p className="marketing-kicker">Current prototype scope</p>
              <dl><div><dt>Operational validation</dt><dd>NVDAx · SPYx · AAPLx</dd></div><div><dt>Validation target</dt><dd>Observed xStock price, with P1a-C and exact-time X-Perp evidence</dd></div><div><dt>Onchain binding</dt><dd>NVDAx · SPYx · AAPLx · X Layer testnet · Chain ID 1952</dd></div><div><dt>Research-only asset</dt><dd>QQQx · not exposed through production HTTP</dd></div><div><dt>Status</dt><dd>Research / hackathon prototype</dd></div></dl>
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
            <a className="primary-link" href="/?view=console">Open validation console <span>↗</span></a>
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
