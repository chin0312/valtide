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
  const earliestDisplayed = displayResults[0];
  const latestDisplayed = displayResults[displayResults.length - 1];

  return (
    <Panel title="Operational evidence timeline" subtitle="Real warmed scheduler observations. The calibrated band and all price series share the same UTC axis.">
      {isLoading ? (
        <p className="text-sm" style={{ color: "var(--color-ink-dim)" }}>Loading operational history…</p>
      ) : isError ? (
        <p className="rounded-lg px-3 py-3 text-sm" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>Operational history unavailable. The current operational result remains authoritative.</p>
      ) : displayResults.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-ink-dim)" }}>No successful operational observations are available yet.</p>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-xs" style={{ color: "var(--color-ink-dim)" }}>
            <span><strong className="tnum text-ink">{displayResults.length}</strong> successful observation{displayResults.length === 1 ? "" : "s"} · {dateTimeUTC(earliestDisplayed?.timestamp)} → {dateTimeUTC(latestDisplayed?.timestamp)}{hasGap ? " · gaps shown" : ""}</span>
            <span className="inline-flex items-center gap-1.5 rounded-lg p-1" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>
              {(Object.keys(OPERATIONAL_HISTORY_LIMITS) as OperationalRange[]).map((option) => (
                <button key={option} onClick={() => onRangeChange(option)} className="rounded px-2.5 py-1 font-mono text-[10px] font-medium" style={option === range ? { background: "var(--color-accent-soft)", color: "var(--color-accent)", border: "1px solid var(--color-accent)" } : { color: "var(--color-muted)", border: "1px solid transparent" }}>{option}</button>
              ))}
            </span>
          </div>
          <EscalationChart results={displayResults} index={index} onSelect={(i) => displayResults[i] && onSelect(displayResults[i].timestamp)} />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs" style={{ color: "var(--color-ink-dim)" }}>
            <span>Selected: <strong className="tnum text-ink">{dateTimeUTC(displayResults[index]?.timestamp)}</strong> · missing scheduler intervals are never interpolated.</span>
            <button onClick={onLatest} disabled={selectedIndex < 0 || index === displayResults.length - 1} className="rounded px-2.5 py-1 font-medium disabled:opacity-40" style={{ color: "var(--color-accent)", background: "var(--color-accent-soft)", border: "1px solid var(--color-line)" }}>
              Back to latest
            </button>
          </div>
        </>
      )}
    </Panel>
  );
}
