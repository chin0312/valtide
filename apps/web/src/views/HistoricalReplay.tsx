import { useEffect } from "react";
import type { ValuationResult } from "../api/types";
import { EscalationChart } from "../components/EscalationChart";
import { EvidenceChip } from "../components/EvidenceChip";
import { Panel } from "../components/ui";
import { Icon } from "../components/Icon";
import { coverageLabel, money, timeUTC } from "../lib/format";
import { advancePosition, clampPosition } from "../lib/playback";

export function HistoricalReplay({
  results,
  position,
  setPosition,
  playing,
  setPlaying,
  sourceLabel,
  showPlayback = true,
}: {
  results: ValuationResult[];
  position: number;
  setPosition: (position: number) => void;
  playing: boolean;
  setPlaying: (playing: boolean) => void;
  sourceLabel: string;
  showPlayback?: boolean;
}) {
  useEffect(() => {
    if (!playing) return;
    if (position >= results.length - 1) {
      setPlaying(false);
      return;
    }
    const origin = clampPosition(position, results.length);
    // Both timestamps must come from RAF. Its first timestamp can precede
    // performance.now() at effect setup, otherwise producing index -1.
    let startedAt: number | undefined;
    let frame = 0;
    const tick = (now: number) => {
      startedAt ??= now;
      const next = advancePosition(origin, now - startedAt, results.length);
      setPosition(next);
      if (next >= results.length - 1) setPlaying(false);
      else frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // Position is intentionally captured at playback start. Adding it here
    // would restart the clock on every animation frame.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, results.length, setPlaying, setPosition]);

  const index = Math.floor(clampPosition(position, results.length));
  const current = results[index];
  const atEnd = position >= results.length - 1;
  const targets = [...new Set(results.map((result) => result.interval_coverage_target))];
  const intervalLabel = targets.length === 1 ? coverageLabel(targets[0]) : "Calibrated interval";

  return (
    <Panel
      title="NVDAx valuation signal"
      icon="signal"
      className="flex h-full min-w-0 flex-col"
      right={<span className="rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.04em]" style={{ color: "var(--color-accent)", background: "var(--color-accent-soft)", border: "1px solid var(--color-line)" }}>{sourceLabel}</span>}
    >
      <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="eyebrow" style={{ color: "var(--color-muted)" }}>Selected period</div>
          <div className="mt-1 flex items-center gap-3"><span className="tnum text-xl font-medium text-ink">{money(current.valtide_fair_value)}</span><EvidenceChip state={current.evidence_state} /></div>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-[11px]" style={{ color: "var(--color-muted)" }}>
          <LegendItem color="var(--color-series-valtide)" label="Fair value" />
          <LegendItem color="var(--color-series-reference)" label="Reference" dashed />
          <LegendItem color="var(--color-series-token)" label="Token market" />
          <span title="The translucent area around fair value"><i className="mr-1.5 inline-block h-2.5 w-4 rounded-sm" style={{ background: "var(--color-band-fill)", border: "1px solid var(--color-series-valtide)" }} />{intervalLabel}</span>
        </div>
      </div>

      <EscalationChart results={results} index={index} playhead={position} onSelect={(next) => { setPlaying(false); setPosition(clampPosition(next, results.length)); }} />

      <div className="mt-auto flex flex-wrap items-center gap-3 border-t pt-3" style={{ borderColor: "var(--color-line-subtle)" }}>
        {showPlayback && (
          <button
            onClick={() => {
              if (atEnd) setPosition(0);
              setPlaying(!playing || atEnd);
            }}
            className="inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium"
            style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)", border: "1px solid var(--color-line)" }}
          >
            <Icon name={playing ? "pause" : atEnd ? "replay" : "play"} size={14} />{playing ? "Pause" : atEnd ? "Replay" : "Play"}
          </button>
        )}
        <input
          type="range"
          min={0}
          max={results.length - 1}
          step={showPlayback ? 0.01 : 1}
          value={clampPosition(position, results.length)}
          onChange={(event) => { setPlaying(false); setPosition(clampPosition(Number(event.target.value), results.length)); }}
          className="min-w-[160px] flex-1 accent-[var(--color-accent)]"
          aria-label="Replay period"
        />
        <span className="tnum inline-flex items-center gap-1.5 text-[11px]" style={{ color: "var(--color-muted)" }}><Icon name="clock" size={12} />{timeUTC(current.timestamp)} · {index + 1}/{results.length}</span>
      </div>
    </Panel>
  );
}

function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return <span className="inline-flex items-center gap-1.5"><i className="inline-block w-4" style={{ height: dashed ? 0 : 2, background: dashed ? undefined : color, borderTop: dashed ? `1px dashed ${color}` : undefined }} />{label}</span>;
}
