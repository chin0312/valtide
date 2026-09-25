import { EscalationChart } from "../components/EscalationChart";
import { Panel } from "../components/ui";
import type { ValuationResult } from "../api/types";
import { dateTimeUTC } from "../lib/format";

export type OperationalRange = "1H" | "6H" | "24H" | "7D";
export const OPERATIONAL_HISTORY_LIMITS: Record<OperationalRange, number> = {
  "1H": 12,
  "6H": 72,
  "24H": 288,
  "7D": 2016,
};

const RANGE_MS: Record<OperationalRange, number> = {
  "1H": 60 * 60 * 1000,
  "6H": 6 * 60 * 60 * 1000,
  "24H": 24 * 60 * 60 * 1000,
  "7D": 7 * 24 * 60 * 60 * 1000,
};

export function filterOperationalResults(results: ValuationResult[], range: OperationalRange): ValuationResult[] {
  const ordered = [...results].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  const latestTimestamp = Math.max(...ordered.map((result) => Date.parse(result.timestamp)));
  if (!Number.isFinite(latestTimestamp)) return [];
  const cutoff = latestTimestamp - RANGE_MS[range];
  return ordered.filter((result) => {
    const timestamp = Date.parse(result.timestamp);
    return Number.isFinite(timestamp) && timestamp > cutoff && timestamp <= latestTimestamp;
  });
}

export function OperationalTimeline({
  results,
  selectedTimestamp,
  onSelect,
  range,
  onRangeChange,
  onLatest,
  isLoading,
  isError,
}: {
  results: ValuationResult[];
  selectedTimestamp: string;
  onSelect: (timestamp: string) => void;
  range: OperationalRange;
  onRangeChange: (range: OperationalRange) => void;
  onLatest: () => void;
  isLoading: boolean;
  isError: boolean;
}) {
  const displayResults = filterOperationalResults(results, range);
  const selectedIndex = displayResults.findIndex((result) => result.timestamp === selectedTimestamp);
  const index = selectedIndex >= 0 ? selectedIndex : Math.max(0, displayResults.length - 1);
  const hasGap = displayResults.some((result, i) => i > 0 && (Date.parse(result.timestamp) - Date.parse(displayResults[i - 1].timestamp)) > 5 * 60 * 1000);
  const latestDisplayed = displayResults[displayResults.length - 1];

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
            <span>{displayResults.length} successful observation{displayResults.length === 1 ? "" : "s"} in the trailing {range} window{hasGap ? "; scheduler gaps are not interpolated" : ""}.</span>
            <span className="inline-flex items-center gap-1.5">
              <span>Range</span>
              {(Object.keys(OPERATIONAL_HISTORY_LIMITS) as OperationalRange[]).map((option) => (
                <button key={option} onClick={() => onRangeChange(option)} className="rounded px-1.5 py-0.5 font-semibold" style={option === range ? { background: "var(--color-accent)", color: "#fff" } : { background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>{option}</button>
              ))}
              <span className="ml-2">Selected: <strong className="text-ink">{dateTimeUTC(displayResults[index]?.timestamp)}</strong></span>
              <span className="ml-2">Latest successful observation: <strong className="text-ink">{dateTimeUTC(latestDisplayed?.timestamp)}</strong></span>
            </span>
          </div>
          <EscalationChart results={displayResults} index={index} onSelect={(i) => displayResults[i] && onSelect(displayResults[i].timestamp)} />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs" style={{ color: "var(--color-ink-dim)" }}>
            <span>Use the chart to inspect a real successful observation; missing scheduler intervals are not interpolated.</span>
            <button onClick={onLatest} disabled={selectedIndex < 0 || index === displayResults.length - 1} className="rounded-md px-2.5 py-1 font-semibold disabled:opacity-40" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>
              Back to latest
            </button>
          </div>
        </>
      )}
    </Panel>
  );
}
