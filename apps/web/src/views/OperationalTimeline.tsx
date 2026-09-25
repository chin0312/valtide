import { EscalationChart } from "../components/EscalationChart";
import { Panel } from "../components/ui";
import type { ValuationResult } from "../api/types";
import { timeUTC } from "../lib/format";

export type OperationalRange = "1H" | "6H" | "24H" | "7D";
export const OPERATIONAL_HISTORY_LIMITS: Record<OperationalRange, number> = {
  "1H": 12,
  "6H": 72,
  "24H": 288,
  "7D": 2016,
};

export function OperationalTimeline({
  results,
  selectedTimestamp,
  onSelect,
  range,
  onRangeChange,
  isLoading,
  isError,
}: {
  results: ValuationResult[];
  selectedTimestamp: string;
  onSelect: (timestamp: string) => void;
  range: OperationalRange;
  onRangeChange: (range: OperationalRange) => void;
  isLoading: boolean;
  isError: boolean;
}) {
  const selectedIndex = results.findIndex((result) => result.timestamp === selectedTimestamp);
  const index = selectedIndex >= 0 ? selectedIndex : Math.max(0, results.length - 1);
  const hasGap = results.some((result, i) => i > 0 && (Date.parse(result.timestamp) - Date.parse(results[i - 1].timestamp)) > 5 * 60 * 1000);

  return (
    <Panel title="Operational history" subtitle="Successful warmed scheduler observations only — this is not a backtest.">
      {isLoading ? (
        <p className="text-sm" style={{ color: "var(--color-ink-dim)" }}>Loading operational history…</p>
      ) : isError ? (
        <p className="rounded-lg px-3 py-3 text-sm" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>Operational history unavailable. The current operational result remains authoritative.</p>
      ) : results.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-ink-dim)" }}>No successful operational observations are available yet.</p>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs" style={{ color: "var(--color-ink-dim)" }}>
            <span>{results.length} successful observation{results.length === 1 ? "" : "s"} available since canonical runtime start{hasGap ? "; scheduler gaps are not interpolated" : ""}.</span>
            <span className="inline-flex items-center gap-1.5">
              <span>Range</span>
              {(Object.keys(OPERATIONAL_HISTORY_LIMITS) as OperationalRange[]).map((option) => (
                <button key={option} onClick={() => onRangeChange(option)} className="rounded px-1.5 py-0.5 font-semibold" style={option === range ? { background: "var(--color-accent)", color: "#fff" } : { background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>{option}</button>
              ))}
              <span className="ml-2">Selected: <strong className="text-ink">{timeUTC(results[index]?.timestamp)}</strong></span>
            </span>
          </div>
          <EscalationChart results={results} index={index} onSelect={(i) => results[i] && onSelect(results[i].timestamp)} />
          <div className="mt-3 flex flex-wrap gap-1.5">
            {results.map((result, i) => (
              <button
                key={`${result.timestamp}-${i}`}
                onClick={() => onSelect(result.timestamp)}
                className="rounded-md px-2 py-1 text-[11px] font-medium"
                style={result.timestamp === selectedTimestamp ? { background: "var(--color-accent)", color: "#fff" } : { background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}
                title={result.timestamp}
              >
                {timeUTC(result.timestamp)}
              </button>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
