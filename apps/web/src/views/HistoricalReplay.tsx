import { useEffect } from "react";
import type { ValuationResult } from "../api/types";
import { EscalationChart } from "../components/EscalationChart";
import { EvidenceChip } from "../components/EvidenceChip";
import { Panel } from "../components/ui";
import { money, sigma, timeUTC } from "../lib/format";
import { EVIDENCE } from "../lib/evidence";

// Step through the deterministic scenario and watch the Evidence State change as
// the reference price drifts away from the challenger's calibrated interval.
export function HistoricalReplay({
  results,
  index,
  setIndex,
  playing,
  setPlaying,
}: {
  results: ValuationResult[];
  index: number;
  setIndex: (i: number) => void;
  playing: boolean;
  setPlaying: (p: boolean) => void;
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
      title="Deterministic scenario replay"
      subtitle="Each point is a 5-minute snapshot. This scenario shows state progression only; it has no empirical future ground truth or model track record."
    >
      <Legend />
      <EscalationChart results={results} index={index} onSelect={setIndex} />

      {/* plain caption for the currently selected step */}
      <div
        className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg px-3 py-2 text-sm"
        style={{ background: EVIDENCE[r.evidence_state].soft, border: `1px solid ${EVIDENCE[r.evidence_state].line}` }}
      >
        <span className="tnum font-medium text-ink">{timeUTC(r.timestamp)}</span>
        <EvidenceChip state={r.evidence_state} />
        <span style={{ color: "var(--color-ink-dim)" }}>
          reference {money(r.reference_under_test)} vs fair value {money(r.valtide_fair_value)} ·{" "}
          <span className="tnum">{sigma(r.standardized_deviation)}</span> away
        </span>
      </div>

      <div className="mt-4 flex items-center gap-4">
        <button
          onClick={() => {
            if (atEnd) setIndex(0);
            setPlaying(!playing);
          }}
          className="rounded-lg px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
          style={{ background: "var(--color-accent)" }}
        >
          {playing ? "❚❚ Pause" : atEnd ? "↻ Replay from start" : "▶ Play"}
        </button>
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
      </div>
    </Panel>
  );
}

function Legend() {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs" style={{ color: "var(--color-ink-dim)" }}>
      <LegendItem swatch={<span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: "var(--color-supported-soft)", border: "1px solid var(--color-supported-line)" }} />} label="Valtide 90% range" />
      <LegendItem swatch={<span className="inline-block h-0.5 w-4 rounded" style={{ background: "var(--color-supported)" }} />} label="Fair value" />
      <LegendItem swatch={<span className="inline-block h-0 w-4 border-t-2 border-dashed" style={{ borderColor: "var(--color-challenged)" }} />} label="Reference under test" />
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
