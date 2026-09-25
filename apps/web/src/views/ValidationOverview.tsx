import type { ValuationResult } from "../api/types";
import { ReasonCodes } from "../components/ReasonCodes";
import { Figure } from "../components/ui";
import { EVIDENCE } from "../lib/evidence";
import { money, pct, sigma } from "../lib/format";

// The hero. Leads with the economic magnitude (a trader anchors on %, not σ),
// surfaces market quality and the reference identity, and flags a fallback
// calibration honestly instead of shouting a scary statistical claim.
export function ValidationOverview({ r }: { r: ValuationResult }) {
  const s = EVIDENCE[r.evidence_state];
  const dev = r.reference_deviation_pct;
  const dir = dev == null ? "" : dev >= 0 ? "above" : "below";
  const negligible = dev != null && Math.abs(dev) < 0.005;
  const fallbackCalibration = r.reason_codes.includes("CALIBRATION_GLOBAL_FALLBACK");

  return (
    <section className="card-shadow overflow-hidden rounded-sm" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)", borderLeft: `2px solid ${s.fg}` }}>
      <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-5" style={{ borderBottom: "1px solid var(--color-line-subtle)" }}>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.1em]" style={{ color: "var(--color-muted)" }}>Evidence state</div>
          <div className="mt-2 text-[28px] font-medium tracking-[-0.04em]" style={{ color: s.fg }}>{s.label}</div>
          <p className="mt-1 max-w-2xl text-[13px]" style={{ color: "var(--color-ink-dim)" }}>{s.description}</p>
        </div>
        <div className="text-right">
          <div className="font-mono text-[10px] uppercase tracking-[0.08em]" style={{ color: "var(--color-muted)" }}>Standardized deviation</div>
          <div className="tnum mt-2 text-2xl font-medium text-ink">{sigma(r.standardized_deviation)}</div>
        </div>
      </div>

      <div className="px-5 py-4">
        {/* economic magnitude first; σ is secondary */}
        <p className="mb-4 max-w-4xl text-[13px] leading-relaxed text-ink">
          The reference price of <strong>{money(r.reference_under_test)}</strong>{" "}
          {dev == null ? "is compared against " : negligible ? "is in line with " : (
            <>is <strong style={{ color: s.fg }}>{pct(Math.abs(dev))}</strong> {dir} </>
          )}
          Valtide's independent estimate of <strong>{money(r.valtide_fair_value)}</strong>{" "}
          (90% range {money(r.fair_value_lower)}–{money(r.fair_value_upper)})
          {dev != null && !negligible && (
            <>, so it falls {r.standardized_deviation != null && Math.abs(r.standardized_deviation) > 1 ? "outside" : "near the edge of"} the model's confidence range</>
          )}.
        </p>

        {fallbackCalibration && (
          <div className="mb-4 flex items-start gap-2 rounded-sm px-3 py-2 text-xs" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
            <span aria-hidden style={{ color: "var(--color-accent)" }}>△</span>
            <span>
              The confidence range uses a <strong>global fallback calibration</strong> (no session-specific
              fit yet), so treat the width of the range — and the σ figure — with caution.
            </span>
          </div>
        )}

        <div className="grid grid-cols-2 overflow-hidden rounded-sm lg:grid-cols-4" style={{ border: "1px solid var(--color-line-subtle)" }}>
          <Figure label="Reference under test" value={money(r.reference_under_test)} sub={r.reference_under_test_source} hint="The price being validated — the value a protocol currently relies on." />
          <Figure label="Valtide fair value" value={money(r.valtide_fair_value)} sub={`90% range ${money(r.fair_value_lower)} – ${money(r.fair_value_upper)}`} hint="An independent challenger estimate with a calibrated uncertainty range — not a definitive fair value." />
          <Figure label="Tokenized market" value={money(r.token_price)} sub="market quality unavailable" hint="The traded NVDAx price. Weigh it by market quality — thin books produce unreliable prices. Depth/volume are captured on the live path but not yet exposed on the public result payload." />
          <Figure label="Reference deviation" value={pct(dev)} sub={`${sigma(r.standardized_deviation)} vs model range`} hint="Economic gap from the estimate. The σ figure depends on the model's confidence range, which is currently a fallback calibration." />
        </div>

        <div className="mt-5 grid gap-5 border-t pt-5 md:grid-cols-2" style={{ borderColor: "var(--color-line-subtle)" }}>
          <div>
            <div className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.08em]" style={{ color: "var(--color-muted)" }}>Basis breakdown</div>
            <dl className="space-y-1.5 text-sm">
              <Row k="Tokenized market move" v={pct(r.observed_token_move_pct)} />
              <Row k="Model-implied move" v={pct(r.model_implied_move_pct)} />
              <Row k="Unexplained premium / discount" v={pct(r.residual_premium_discount_pct)} hint="The part of the token price the model doesn't explain — not automatically a mispricing." />
            </dl>
          </div>
          <div>
            <div className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.08em]" style={{ color: "var(--color-muted)" }}>Signals behind this verdict</div>
            <ReasonCodes codes={r.reason_codes} />
          </div>
        </div>
      </div>
    </section>
  );
}

function Row({ k, v, hint }: { k: string; v: string; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="flex items-center gap-1.5" style={{ color: "var(--color-ink-dim)" }}>
        {k}
        {hint && (
          <span title={hint} className="inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full text-[9px]" style={{ background: "var(--color-line)", color: "var(--color-ink-dim)" }}>i</span>
        )}
      </dt>
      <dd className="tnum font-medium text-ink">{v}</dd>
    </div>
  );
}
