import type { EvidenceState, ValuationResult } from "../api/types";
import { Panel } from "../components/ui";
import { EVIDENCE } from "../lib/evidence";
import { pct, sigma, sourceLabel, timeUTC } from "../lib/format";

const STATES: EvidenceState[] = ["SUPPORTED", "INCONCLUSIVE", "CHALLENGED"];

export function ObservationRecord({ results, currentIndex, sourceLabelText }: { results: ValuationResult[]; currentIndex: number; sourceLabelText: string }) {
  const counts = STATES.reduce<Record<EvidenceState, number>>((acc, state) => {
    acc[state] = results.filter((result) => result.evidence_state === state).length;
    return acc;
  }, { SUPPORTED: 0, INCONCLUSIVE: 0, CHALLENGED: 0 });
  const transitions = results.filter((result, index) => index > 0 && result.evidence_state !== results[index - 1].evidence_state);
  const breaches = results.filter((result) => result.reference_under_test != null && (result.reference_under_test < result.fair_value_lower || result.reference_under_test > result.fair_value_upper)).length;
  const maxSigma = results.reduce((max, result) => Math.max(max, Math.abs(result.standardized_deviation ?? 0)), 0);
  const current = results[Math.min(currentIndex, results.length - 1)];
  const total = Math.max(results.length, 1);
  const events = results.filter((result, index) => index === 0 || result.evidence_state !== results[index - 1].evidence_state);

  return (
    <Panel
      title="Evidence record"
      right={<span className="rounded px-2 py-1 font-mono text-[9px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)", background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>{sourceLabelText}</span>}
    >
      <div className="grid grid-cols-2 overflow-hidden rounded-lg lg:grid-cols-4" style={{ border: "1px solid var(--color-line-subtle)" }}>
        <RecordMetric label="Observations" value={String(results.length)} />
        <RecordMetric label="State changes" value={String(transitions.length)} />
        <RecordMetric label="Peak deviation" value={sigma(maxSigma)} />
        <RecordMetric label="Outside interval" value={`${breaches}/${results.length}`} />
      </div>

      <div className="mt-4 grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div>
          <div className="mb-2 flex items-center justify-between text-[10px]" style={{ color: "var(--color-muted)" }}>
            <span className="font-mono uppercase tracking-[0.08em]">State distribution</span>
            <span className="tnum">Current · {current?.evidence_state ?? "—"}</span>
          </div>
          <div className="flex h-3 overflow-hidden rounded-sm" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>
            {STATES.map((state) => counts[state] > 0 && <div key={state} style={{ width: `${(counts[state] / total) * 100}%`, background: EVIDENCE[state].fg }} title={`${state}: ${counts[state]}`} />)}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px]">
            {STATES.map((state) => <span key={state} className="inline-flex items-center gap-1.5" style={{ color: "var(--color-ink-dim)" }}><i className="h-2 w-2 rounded-sm" style={{ background: EVIDENCE[state].fg }} />{state} <b className="tnum text-ink">{counts[state]}</b></span>)}
          </div>

          <div className="mt-5 flex min-h-16 items-center gap-1 overflow-hidden">
            {results.map((result, index) => {
              const active = index === currentIndex;
              const style = EVIDENCE[result.evidence_state];
              return <div key={`${result.timestamp}-${index}`} className="min-w-1 flex-1 rounded-sm transition-[height,opacity] duration-150" style={{ height: active ? 40 : 22, background: style.fg, opacity: active ? 1 : 0.42 }} title={`${timeUTC(result.timestamp)} · ${result.evidence_state} · ${sigma(result.standardized_deviation)}`} />;
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-5 gap-y-3 border-t pt-4 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0" style={{ borderColor: "var(--color-line-subtle)" }}>
          <SourceFact label="Token source" value={current?.token_source ? sourceLabel(current.token_source) : current?.token_price != null ? "Demo scenario" : "—"} />
          <SourceFact label="Reference" value={sourceLabel(current?.reference_under_test_source)} />
          <SourceFact label="Model" value={current ? `${current.model_id} ${current.model_version}` : "—"} />
          <SourceFact label="Market state" value={current?.market_state ?? "—"} />
          <SourceFact label="Residual" value={pct(current?.residual_premium_discount_pct)} />
          <SourceFact label="First signal" value={events[0] ? `${timeUTC(events[0].timestamp)} · ${events[0].evidence_state}` : "—"} />
        </div>
      </div>
    </Panel>
  );
}

function RecordMetric({ label, value }: { label: string; value: string }) {
  return <div className="px-3 py-3" style={{ background: "var(--color-panel-2)", borderRight: "1px solid var(--color-line-subtle)" }}><div className="eyebrow" style={{ color: "var(--color-muted)" }}>{label}</div><div className="tnum mt-1.5 text-xl font-medium text-ink">{value}</div></div>;
}

function SourceFact({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><div className="eyebrow" style={{ color: "var(--color-muted)" }}>{label}</div><div className="tnum mt-1 truncate text-[11px] text-ink" title={value}>{value}</div></div>;
}
