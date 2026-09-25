import { useQuery } from "@tanstack/react-query";
import type { EvidenceState, ValuationResult } from "../api/types";
import { fetchBacktest } from "../api/client";
import { Panel } from "../components/ui";
import { EVIDENCE } from "../lib/evidence";

const STATES: EvidenceState[] = ["SUPPORTED", "INCONCLUSIVE", "CHALLENGED"];

// Track record. Pulls real metrics from /api/backtest; falls back to the loaded
// sequence's own verdict distribution when the backend is unreachable, and is
// explicit that accuracy metrics need historical ground truth (not in a scenario).
export function ModelEvidence({ results, source }: { results: ValuationResult[]; source: string }) {
  const { data, isError } = useQuery({
    queryKey: ["backtest", source],
    queryFn: () => fetchBacktest(source),
    staleTime: 60_000,
    retry: 0,
  });

  // Offline fallback: count verdicts from the sequence we already have.
  const counts =
    data?.evidence_state_counts ??
    results.reduce<Record<string, number>>((acc, r) => {
      acc[r.evidence_state] = (acc[r.evidence_state] ?? 0) + 1;
      return acc;
    }, {});
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;

  const hasMetrics = data && data.mae != null && data.interval_coverage != null;

  return (
    <Panel title="Track record" subtitle="How the model has behaved — and how to judge it">
      <div className="mb-2 text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>
        Verdicts across this {data ? data.source : source} window ({total})
      </div>
      <div className="flex h-2 overflow-hidden rounded-sm" style={{ border: "1px solid var(--color-line)" }}>
        {STATES.map((s) => {
          const w = ((counts[s] ?? 0) / total) * 100;
          return w > 0 ? <div key={s} style={{ width: `${w}%`, background: EVIDENCE[s].fg }} title={`${s}: ${counts[s]}`} /> : null;
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {STATES.map((s) => (
          <span key={s} className="inline-flex items-center gap-1.5" style={{ color: "var(--color-ink-dim)" }}>
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: EVIDENCE[s].fg }} />
            {s} {counts[s] ?? 0}
          </span>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-3 overflow-hidden rounded-sm" style={{ border: "1px solid var(--color-line-subtle)" }}>
        <Metric label="Interval coverage" value={hasMetrics ? `${(data!.interval_coverage! * 100).toFixed(0)}%` : "—"} hint="How often the true price landed inside the 90% range. Should be near 90%." />
        <Metric label="Mean abs. error" value={hasMetrics ? `$${data!.mae!.toFixed(2)}` : "—"} hint="Average absolute error of the estimate vs the eventual trusted price." />
        <Metric label="Evaluable points" value={data ? String(data.n_evaluable) : "—"} hint="Observations with a later ground-truth price to score against." />
      </div>

      <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>
        {isError
          ? "Backend unreachable — showing the verdict mix from the loaded demo sequence. Accuracy metrics require the live backend."
          : hasMetrics
            ? data!.note
            : "Accuracy metrics (coverage, error vs. the later benchmark, false-challenge rate) need historical ground-truth data and aren't available for this illustrative scenario. Run the backend against the historical panel to populate them."}
      </p>
    </Panel>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="px-3 py-3" style={{ background: "var(--color-panel)", borderRight: "1px solid var(--color-line-subtle)" }}>
      <div className="flex items-center gap-1 font-mono text-[9px] font-medium uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)" }} title={hint}>
        {label}
        <span className="inline-flex h-3 w-3 cursor-help items-center justify-center rounded-full text-[8px]" style={{ background: "var(--color-line)" }}>i</span>
      </div>
      <div className="tnum mt-2 text-lg font-medium text-ink">{value}</div>
    </div>
  );
}
