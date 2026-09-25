import type { ValuationResult } from "../api/types";
import { EvidenceChip } from "../components/EvidenceChip";
import { ReasonCodes } from "../components/ReasonCodes";
import { Figure } from "../components/ui";
import { EVIDENCE } from "../lib/evidence";
import { compactUsd, coverageLabel, dateTimeUTC, money, pct, reasonLabel, sigma, sourceLabel } from "../lib/format";

const ABSTENTION_GATES = [
  "TOKEN_DATA_UNAVAILABLE",
  "COMPARATOR_UNAVAILABLE",
  "MODEL_UNCERTAINTY_INVALID",
  "UNDERLYING_REFERENCE_STALE",
  "REFERENCE_UNDER_TEST_STALE",
  "TOKEN_MARKET_QUALITY_LOW",
  "TOKEN_UNIT_SUSPECT",
  "MODEL_UNCERTAINTY_HIGH",
];

export function ValidationOverview({ r }: { r: ValuationResult }) {
  const state = EVIDENCE[r.evidence_state];
  const coverage = coverageLabel(r.interval_coverage_target);
  const outsideInterval = r.reference_under_test != null && (r.reference_under_test < r.fair_value_lower || r.reference_under_test > r.fair_value_upper);
  const fallbackCalibration = r.reason_codes.includes("CALIBRATION_GLOBAL_FALLBACK");
  const gate = ABSTENTION_GATES.find((code) => r.reason_codes.includes(code));
  const provenance = Object.entries(r.source_provenance ?? {}).map(([source, value]) => `${source}: ${value}`).join(" · ");

  return (
    <section className="overflow-hidden rounded-[10px]" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)", borderLeft: `2px solid ${state.fg}` }}>
      <div className="flex flex-wrap items-start justify-between gap-5 border-b px-5 py-5" style={{ borderColor: "var(--color-line-subtle)" }}>
        <div className="max-w-3xl">
          <div className="eyebrow" style={{ color: "var(--color-muted)" }}>Evidence State</div>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h2 className="text-[30px] font-semibold tracking-[-0.04em]" style={{ color: state.fg }}>{state.label}</h2>
            <EvidenceChip state={r.evidence_state} />
          </div>
          <p className="mt-1.5 text-[13px] leading-5" style={{ color: "var(--color-ink-dim)" }}>{verdictNarrative(r, outsideInterval, gate)}</p>
        </div>
        <div className="min-w-[150px] text-left sm:text-right">
          <div className="eyebrow" style={{ color: "var(--color-muted)" }}>Standardized Deviation</div>
          <div className="tnum mt-2 text-[28px] font-medium tracking-[-0.04em] text-ink">{sigma(r.standardized_deviation)}</div>
          {fallbackCalibration && (
            <span className="mt-2 inline-flex rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.04em]" style={{ color: "var(--color-inconclusive)", background: "var(--color-inconclusive-soft)", border: "1px solid var(--color-inconclusive-line)" }}>
              Fallback Calibration
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 overflow-hidden border-b lg:grid-cols-4" style={{ borderColor: "var(--color-line-subtle)" }}>
        <Figure label="Reference Under Test" value={money(r.reference_under_test)} sub={sourceLabel(r.reference_under_test_source)} />
        <Figure label="Valtide Fair Value" value={money(r.valtide_fair_value)} sub={`${coverage}: ${money(r.fair_value_lower)}–${money(r.fair_value_upper)}`} />
        <Figure label="Tokenized Market" value={money(r.token_price)} sub={sourceLabel(r.token_source)} />
        <Figure label="Reference Deviation" value={pct(r.reference_deviation_pct)} sub={outsideInterval ? "Outside Calibrated Interval" : "Inside Calibrated Interval"} />
      </div>

      <div className="grid gap-5 px-5 py-4 md:grid-cols-2">
        <div>
          <div className="eyebrow mb-2" style={{ color: "var(--color-muted)" }}>Basis Breakdown</div>
          <dl className="space-y-1.5 text-xs">
            <Row k="Tokenized Market Move" v={pct(r.observed_token_move_pct)} />
            <Row k="Model-Implied Move" v={pct(r.model_implied_move_pct)} />
            <Row k="Unexplained Premium / Discount" v={pct(r.residual_premium_discount_pct)} />
          </dl>
        </div>
        <div>
          <div className="eyebrow mb-2" style={{ color: "var(--color-muted)" }}>Signals Behind This State</div>
          <ReasonCodes codes={r.reason_codes} evidenceState={r.evidence_state} />
        </div>
      </div>

      <details className="border-t px-5 py-3" style={{ borderColor: "var(--color-line-subtle)" }}>
        <summary className="flex items-center justify-between text-xs" style={{ color: "var(--color-ink-dim)" }}>
          <span>Technical Evidence And Provenance</span><span aria-hidden style={{ color: "var(--color-accent)" }}>＋</span>
        </summary>
        <dl className="mt-4 grid gap-x-8 gap-y-2 text-xs sm:grid-cols-2">
          <Row k="Token Observed" v={dateTimeUTC(r.token_observed_at)} />
          <Row k="Reference Observed" v={dateTimeUTC(r.reference_under_test_ts)} />
          <Row k="Token Volume" v={r.token_volume == null ? "—" : r.token_volume.toFixed(2)} />
          <Row k="Token Volume USD" v={compactUsd(r.token_volume_usd)} />
          <Row k="Token Liquidity" v={compactUsd(r.token_liquidity_usd)} />
          <Row k="Provenance" v={provenance || "—"} />
        </dl>
        {fallbackCalibration && <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>The interval uses a global fallback calibration, so its width and the standardized deviation should be interpreted cautiously.</p>}
      </details>
    </section>
  );
}

function verdictNarrative(r: ValuationResult, outsideInterval: boolean, gate?: string): string {
  if (r.reference_under_test == null) return `No reference under test is available. Valtide's independent estimate is ${money(r.valtide_fair_value)}.`;
  if (r.evidence_state === "INCONCLUSIVE" && gate) return `Valtide abstains because ${reasonLabel(gate).toLowerCase()}. The reference is ${outsideInterval ? "outside" : "inside"} the calibrated interval.`;
  if (r.evidence_state === "INCONCLUSIVE" && outsideInterval) return `The reference is outside ${money(r.fair_value_lower)}–${money(r.fair_value_upper)}, but the combined evidence did not meet the backend's challenge rule, so Valtide abstains.`;
  if (r.evidence_state === "CHALLENGED") return `The reference at ${money(r.reference_under_test)} is materially inconsistent with Valtide's ${money(r.fair_value_lower)}–${money(r.fair_value_upper)} interval. This is evidence for review, not proof the reference is wrong.`;
  return `The reference at ${money(r.reference_under_test)} is supported by the available independent evidence and sits ${outsideInterval ? "outside" : "inside"} Valtide's calibrated interval.`;
}

function Row({ k, v }: { k: string; v: string }) {
  return <div className="flex min-w-0 items-start justify-between gap-4"><dt style={{ color: "var(--color-muted)" }}>{k}</dt><dd className="tnum max-w-[65%] truncate text-right font-medium text-ink" title={v}>{v}</dd></div>;
}
