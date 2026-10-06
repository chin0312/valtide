import { useQuery } from "@tanstack/react-query";
import type { EvidenceState } from "../api/types";
import { assetQueryKeys, fetchHistoricalBacktest } from "../api/client";
import { Panel } from "../components/ui";
import { EVIDENCE } from "../lib/evidence";
import { dateTimeUTC } from "../lib/format";

const STATES: EvidenceState[] = ["SUPPORTED", "INCONCLUSIVE", "CHALLENGED"];

// Historical evidence is deliberately separate from the deterministic scenario.
// Scenario verdict counts are not future ground truth and must not be presented
// as a track record or accuracy result.
export function ModelEvidence({ asset, profile }: { asset: string; profile: string }) {
  const { data, isError, isLoading } = useQuery({
    queryKey: assetQueryKeys.backtest(asset, profile),
    queryFn: () => fetchHistoricalBacktest(asset),
    staleTime: 60_000,
    retry: 0,
  });

  const counts = data?.evidence_state_counts ?? {};
  const total = data ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;
  const hasMetrics = data && data.mae != null && data.rmse != null && data.interval_coverage != null;

  return (
    <Panel title="Selected Historical Evidence" subtitle="A summary of product Evidence States from the selected historical panel, separate from the Demo scenario.">
      {isError || !data ? (
        <div className="rounded-lg px-3 py-3 text-sm" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
          {isLoading ? "Loading historical model evidence…" : "Historical model evidence unavailable. Scenario verdicts are not empirical performance evidence."}
        </div>
      ) : (
        <>
          <p className="mb-4 rounded-lg px-3 py-3 text-xs leading-5" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>These counts describe how the shared backend validation pipeline classified historical observations; they are not an accuracy score or a performance guarantee.</p>
          <div className="mb-2 text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>
            Evidence States Across Historical Observations ({total})
          </div>
          <div className="mb-3 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2" style={{ color: "var(--color-ink-dim)" }}>
            <span>Historical window: <strong className="text-ink">{dateTimeUTC(data.window_start)} → {dateTimeUTC(data.window_end)}</strong></span>
            <span>Model runtime: <strong className="text-ink">{data.model_id ?? "—"} {data.model_version ?? ""}</strong></span>
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

          <div className="mt-4 grid grid-cols-1 overflow-hidden rounded-lg sm:grid-cols-3" style={{ border: "1px solid var(--color-line)" }}>
            <Metric label="Observations" value={String(data.n_observations)} hint="Rows in this selected historical window." />
            <Metric label="Observations With A Contemporaneous Benchmark" value={String(data.n_evaluable)} hint="Used for retrospective error diagnostics, not as a runtime Evidence State vote." />
            <Metric label="Benchmark Coverage" value={hasMetrics ? `${(data.interval_coverage! * 100).toFixed(0)}%` : "—"} hint="Coverage of the calibrated interval against the contemporaneous benchmark; interval membership does not determine Evidence State." />
          </div>

          <details className="mt-3 rounded-lg" style={{ border: "1px solid var(--color-line)" }}>
            <summary className="cursor-pointer px-3 py-2.5 text-xs text-ink-dim">Advanced Point-Error Diagnostics</summary>
            <div className="grid grid-cols-1 border-t sm:grid-cols-2" style={{ borderColor: "var(--color-line)" }}><Metric label="Mean Absolute Error" value={hasMetrics ? `$${data.mae!.toFixed(2)}` : "—"} hint="Average distance from the contemporaneous benchmark; no competitor comparison is available." /><Metric label="Root Mean Squared Error" value={hasMetrics ? `$${data.rmse!.toFixed(2)}` : "—"} hint="An error measure that gives more weight to larger misses; no competitor comparison is available." /></div>
          </details>

          <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>{data.note}</p>
        </>
      )}
    </Panel>
  );
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="px-3 py-2.5" style={{ background: "var(--color-panel-2)", borderRight: "1px solid var(--color-line)" }}>
      <div className="eyebrow" style={{ color: "var(--color-muted)" }}>{label}</div>
      <div className="tnum mt-1.5 text-xl font-medium text-ink">{value}</div>
      <div className="mt-1 text-[10px] leading-4 text-muted">{hint}</div>
    </div>
  );
}
