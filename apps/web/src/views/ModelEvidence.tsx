import { useQuery } from "@tanstack/react-query";
import type { EvidenceState } from "../api/types";
import { fetchHistoricalBacktest } from "../api/client";
import { Panel } from "../components/ui";
import { EVIDENCE } from "../lib/evidence";
import { timeUTC } from "../lib/format";

const STATES: EvidenceState[] = ["SUPPORTED", "INCONCLUSIVE", "CHALLENGED"];

// Historical evidence is deliberately separate from the deterministic scenario.
// Scenario verdict counts are not future ground truth and must not be presented
// as a track record or accuracy result.
export function ModelEvidence() {
  const { data, isError } = useQuery({
    queryKey: ["backtest", "historical"],
    queryFn: fetchHistoricalBacktest,
    staleTime: 60_000,
    retry: 0,
  });

  const counts = data?.evidence_state_counts ?? {};
  const total = data ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;
  const hasMetrics = data && data.mae != null && data.rmse != null && data.interval_coverage != null;

  return (
    <Panel title="Historical model evidence" subtitle="Historical diagnostics, separate from the deterministic scenario replay">
      {isError || !data ? (
        <div className="rounded-lg px-3 py-3 text-sm" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
          Historical model evidence unavailable. Scenario verdicts are not empirical performance evidence.
        </div>
      ) : (
        <>
          <div className="mb-2 text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>
            Evidence States across historical observations ({total})
          </div>
          <div className="mb-3 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2" style={{ color: "var(--color-ink-dim)" }}>
            <span>Window: <strong className="text-ink">{timeUTC(data.window_start)} → {timeUTC(data.window_end)}</strong></span>
            <span>Model: <strong className="text-ink">{data.model_id ?? "—"} {data.model_version ?? ""}</strong></span>
          </div>
          <div className="flex h-3 overflow-hidden rounded-full" style={{ border: "1px solid var(--color-line)" }}>
            {STATES.map((s) => {
              const w = total ? ((counts[s] ?? 0) / total) * 100 : 0;
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

          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Metric label="Observations" value={String(data.n_observations)} hint="Rows in the historical replay." />
            <Metric label="Evaluable points" value={String(data.n_evaluable)} hint="Rows with a legitimate contemporaneous trusted benchmark." />
            <Metric label="MAE" value={hasMetrics ? `$${data.mae!.toFixed(2)}` : "—"} hint="Mean absolute error against the historical benchmark." />
            <Metric label="RMSE" value={hasMetrics ? `$${data.rmse!.toFixed(2)}` : "—"} hint="Root mean squared error against the historical benchmark." />
            <Metric label="Interval coverage" value={hasMetrics ? `${(data.interval_coverage! * 100).toFixed(0)}%` : "—"} hint="Historical share of benchmark observations inside the calibrated interval." />
          </div>

          <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>{data.note} These are historical diagnostics, not production guarantees.</p>
        </>
      )}
    </Panel>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg px-3 py-2.5" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>
      <div className="flex items-center gap-1 text-[11px] font-medium" style={{ color: "var(--color-ink-dim)" }} title={hint}>
        {label}
        <span className="inline-flex h-3 w-3 cursor-help items-center justify-center rounded-full text-[8px]" style={{ background: "var(--color-line)" }}>i</span>
      </div>
      <div className="tnum mt-1 text-xl font-semibold text-ink">{value}</div>
    </div>
  );
}
