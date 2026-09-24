import type { ValuationResult } from "../api/types";
import { EvidenceChip } from "../components/EvidenceChip";
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
  const outsideInterval = r.reference_under_test != null && (r.reference_under_test < r.fair_value_lower || r.reference_under_test > r.fair_value_upper);
  const coverage = `${Math.round(r.interval_coverage_target * 100)}%`;
  const fallbackCalibration = r.reason_codes.includes("CALIBRATION_GLOBAL_FALLBACK");

  return (
    <section className="card-shadow overflow-hidden rounded-2xl bg-white" style={{ border: "1px solid var(--color-line)" }}>
      <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-5" style={{ background: s.soft, borderBottom: `1px solid ${s.line}` }}>
        <div>
          <div className="text-xl font-semibold" style={{ color: s.fg }}>{s.headline}</div>
          <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--color-ink-dim)" }}>{s.description}</p>
        </div>
        <EvidenceChip state={r.evidence_state} size="lg" />
      </div>

      <div className="p-6">
        {/* economic magnitude first; σ is secondary */}
        <p className="mb-4 text-[15px] leading-relaxed text-ink">
          {r.reference_under_test == null ? (
            <>No reference under test is available at this observation. Valtide's independent challenger estimate is <strong>{money(r.valtide_fair_value)}</strong> ({coverage} calibrated interval {money(r.fair_value_lower)}–{money(r.fair_value_upper)}).</>
          ) : (
            <>The reference under test at <strong>{money(r.reference_under_test)}</strong>{" "}
              {dev == null ? "is compared against " : negligible ? "is close to " : (
                <>is <strong style={{ color: s.fg }}>{pct(Math.abs(dev))}</strong> {dir} </>
              )}
              Valtide's independent challenger estimate of <strong>{money(r.valtide_fair_value)}</strong>{" "}
              ({coverage} calibrated interval {money(r.fair_value_lower)}–{money(r.fair_value_upper)}), so it is {outsideInterval ? "outside" : "inside"} Valtide's {coverage} calibrated challenger interval.
            </>
          )}
        </p>

        {fallbackCalibration && (
          <div className="mb-4 flex items-start gap-2 rounded-lg px-3 py-2 text-sm" style={{ background: "var(--color-inconclusive-soft)", border: "1px solid var(--color-inconclusive-line)", color: "var(--color-inconclusive)" }}>
            <span aria-hidden>⚠</span>
            <span>
              The calibrated interval uses a <strong>global fallback calibration</strong> (no session-specific
              fit yet), so treat the width of the interval — and the σ figure — with caution.
            </span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Figure label="Reference under test" value={money(r.reference_under_test)} sub={r.reference_under_test_source} hint="The price being validated — the value a protocol currently relies on." />
          <Figure label="Valtide challenger estimate" value={money(r.valtide_fair_value)} sub={`${coverage} calibrated interval ${money(r.fair_value_lower)} – ${money(r.fair_value_upper)}`} accent="var(--color-supported)" hint="An independent challenger estimate with a calibrated uncertainty interval — not a definitive fair value." />
          <Figure label="Tokenized market" value={money(r.token_price)} sub="depth / volume not in result" accent="var(--color-token)" hint="The traded NVDAx price. Weigh it by market quality — thin books produce unreliable prices. Depth/volume are captured on the live path but not yet exposed on the public result payload." />
          <Figure label="Deviation" value={pct(dev)} sub={`${sigma(r.standardized_deviation)} diagnostic`} accent={s.fg} hint="Economic gap from the challenger estimate. The Evidence State also uses interval bounds and evidence quality." />
        </div>

        <div className="mt-5 grid gap-5 border-t pt-5 md:grid-cols-2" style={{ borderColor: "var(--color-line)" }}>
          <div>
            <div className="mb-2 text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>How the price moved</div>
            <dl className="space-y-1.5 text-sm">
              <Row k="Tokenized market move" v={pct(r.observed_token_move_pct)} />
              <Row k="Model-implied move" v={pct(r.model_implied_move_pct)} />
              <Row k="Unexplained premium / discount" v={pct(r.residual_premium_discount_pct)} hint="The part of the token price the model doesn't explain — not automatically a mispricing." />
            </dl>
          </div>
          <div>
            <div className="mb-2 text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>Signals behind this verdict</div>
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
