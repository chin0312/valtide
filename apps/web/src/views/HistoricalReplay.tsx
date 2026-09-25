import { useEffect } from "react";
import type { ValuationResult } from "../api/types";
import { EscalationChart } from "../components/EscalationChart";
import { EvidenceChip } from "../components/EvidenceChip";
import { Panel } from "../components/ui";
import { coverageLabel, dateTimeUTC, money, timeUTC } from "../lib/format";
import { EVIDENCE } from "../lib/evidence";

// Step through the deterministic scenario and watch the Evidence State change as
// the reference price drifts away from the challenger's calibrated interval.
export function HistoricalReplay({
  results,
  index,
  setIndex,
  playing,
  setPlaying,
  title = "Deterministic 25-minute scenario",
  subtitle = "Six five-minute snapshots show state progression only; this is not operational history or model performance evidence.",
  showPlayback = true,
  fullTimestamps = false,
  showLatest = false,
  onLatest,
}: {
  results: ValuationResult[];
  index: number;
  setIndex: (i: number) => void;
  playing: boolean;
  setPlaying: (p: boolean) => void;
  title?: string;
  subtitle?: string;
  showPlayback?: boolean;
  fullTimestamps?: boolean;
  showLatest?: boolean;
  onLatest?: () => void;
}) {
  useEffect(() => {
    if (!playing) return;
    if (index >= results.length - 1) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setIndex(index + 1), 1100);
    return () => clearTimeout(t);
  }, [playing, index, results.length, setIndex, setPlaying]);

  const r = results[index];
  const atEnd = index >= results.length - 1;

  return (
    <Panel
      title={title}
      subtitle={subtitle}
    >
      <Legend results={results} />
      <EscalationChart results={results} index={index} onSelect={setIndex} />

      {/* plain caption for the currently selected step */}
      <div
        className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg px-3 py-2 text-xs"
        style={{ background: "var(--color-panel-2)", border: `1px solid ${EVIDENCE[r.evidence_state].line}` }}
      >
        <span className="tnum font-medium text-ink">{fullTimestamps ? dateTimeUTC(r.timestamp) : timeUTC(r.timestamp)}</span>
        <EvidenceChip state={r.evidence_state} />
        <span style={{ color: "var(--color-ink-dim)" }}>
          reference {money(r.reference_under_test)} vs fair value {money(r.valtide_fair_value)}
        </span>
      </div>

      <div className="mt-4 flex items-center gap-4">
        {showPlayback && <button
          onClick={() => {
            if (atEnd) setIndex(0);
            setPlaying(!playing);
          }}
          className="rounded px-4 py-2 text-xs font-medium transition-colors"
          style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)", border: "1px solid var(--color-accent)" }}
        >
          {playing ? "❚❚ Pause" : atEnd ? "↻ Replay from start" : "▶ Play"}
        </button>}
        <input
          type="range"
          min={0}
          max={results.length - 1}
          value={index}
          onChange={(e) => {
            setPlaying(false);
            setIndex(Number(e.target.value));
          }}
          className="flex-1 accent-[var(--color-accent)]"
          aria-label="Replay step"
        />
        <span className="tnum text-sm" style={{ color: "var(--color-ink-dim)" }}>
          step {index + 1} / {results.length}
        </span>
        {showLatest && <button
          onClick={onLatest}
          disabled={atEnd}
          className="rounded-lg px-3 py-2 text-xs font-semibold disabled:opacity-40"
          style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}
        >
          Latest panel point
        </button>}
      </div>
    </Panel>
  );
}

function Legend({ results }: { results: ValuationResult[] }) {
  const targets = [...new Set(results.map((result) => result.interval_coverage_target))];
  const intervalLabel = targets.length === 1 ? coverageLabel(targets[0]) : "Calibrated interval";
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs" style={{ color: "var(--color-ink-dim)" }}>
      <LegendItem swatch={<span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: "var(--color-band-fill)", border: "1px solid var(--color-series-valtide)" }} />} label={`Valtide ${intervalLabel}`} />
      <LegendItem swatch={<span className="inline-block h-0.5 w-4" style={{ background: "var(--color-series-valtide)" }} />} label="Fair value" />
      <LegendItem swatch={<span className="inline-block h-0 w-4 border-t border-dashed" style={{ borderColor: "var(--color-series-reference)" }} />} label="Reference under test" />
      <LegendItem swatch={<span className="inline-block h-0.5 w-4" style={{ background: "var(--color-series-token)" }} />} label="Tokenized market" />
    </div>
  );
}

function LegendItem({ swatch, label }: { swatch: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {swatch}
      {label}
    </span>
  );
}
