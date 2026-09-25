import { useEffect, type Dispatch, type SetStateAction, type ReactNode } from "react";
import type { ValuationResult } from "../api/types";
import { EscalationChart } from "../components/EscalationChart";
import { EvidenceChip } from "../components/EvidenceChip";
import { Panel } from "../components/ui";
import { Icon } from "../components/Icon";
import { coverageLabel, money, dateTimeUTC } from "../lib/format";
import { advancePosition, clampPosition } from "../lib/playback";

export function HistoricalReplay({
  results,
  position,
  setPosition,
  playing,
  setPlaying,
  sourceLabel,
  showPlayback = true,
  onReview,
  onLatest,
  onResetView,
  followingLatest = false,
  rangeControl,
  periodMs = 120,
}: {
  results: ValuationResult[];
  position: number;
  setPosition: Dispatch<SetStateAction<number>>;
  playing: boolean;
  setPlaying: (playing: boolean) => void;
  sourceLabel: string;
  showPlayback?: boolean;
  onReview?: () => void;
  onLatest?: () => void;
  onResetView?: () => void;
  followingLatest?: boolean;
  rangeControl?: ReactNode;
  periodMs?: number;
}) {
  useEffect(() => {
    if (!playing) return;
    // Increment from the current position so a rolling history refresh can
    // rebase the selection without the animation jumping to its old index.
    let lastFrame: number | undefined;
    let frame = 0;
    const tick = (now: number) => {
      const elapsed = lastFrame == null ? 0 : now - lastFrame;
      lastFrame = now;
      setPosition((value) => advancePosition(value, elapsed, results.length, periodMs));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, results.length, setPosition, periodMs]);

  useEffect(() => {
    if (playing && position >= results.length - 1) setPlaying(false);
  }, [playing, position, results.length, setPlaying]);

  const index = Math.floor(clampPosition(position, results.length));
  const current = results[index];
  const atEnd = position >= results.length - 1;
  const targets = [...new Set(results.map((result) => result.interval_coverage_target))];
  const intervalLabel = targets.length === 1 ? coverageLabel(targets[0]) : "Calibrated interval";
  const gaps = results.slice(1).filter((result, i) => Date.parse(result.timestamp) - Date.parse(results[i].timestamp) > 5 * 60_000).length;

  return (
    <Panel
      title="NVDAx valuation signal"
      icon="signal"
      className="flex h-full min-w-0 flex-col"
      right={<span className="rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.04em]" style={{ color: "var(--color-accent)", background: "var(--color-accent-soft)", border: "1px solid var(--color-line)" }}>{sourceLabel}</span>}
    >
      <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
        {rangeControl && <div className="flex w-full justify-end gap-2">{rangeControl}{onResetView && <button type="button" onClick={onResetView} className="rounded px-2 py-1 text-[10px]" style={{ color: "var(--color-muted)" }}>Reset</button>}</div>}
        <div>
          <div className="eyebrow" style={{ color: "var(--color-muted)" }}>{followingLatest ? "Latest observation" : "Selected period"}</div>
          <div className="mt-1 flex items-center gap-3"><span className="tnum text-xl font-medium text-ink">{money(current.valtide_fair_value)}</span><EvidenceChip state={current.evidence_state} /></div>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-[11px]" style={{ color: "var(--color-muted)" }}>
          <LegendItem color="var(--color-series-valtide)" label="Fair value" />
          <LegendItem color="var(--color-series-reference)" label="Reference" dashed />
          <LegendItem color="var(--color-series-token)" label="Token market" />
          <span title="The translucent area around fair value"><i className="mr-1.5 inline-block h-2.5 w-4 rounded-sm" style={{ background: "var(--color-band-fill)", border: "1px solid var(--color-series-valtide)" }} />{intervalLabel}</span>
          {gaps > 0 && <span tabIndex={0} title="No recorded observations in these intervals. Missing prices are not filled in." aria-label={`${gaps} data gaps: no recorded observations; missing prices are not filled in.`}>{gaps} data gaps</span>}
        </div>
      </div>

      <EscalationChart results={results} index={index} playhead={position} onSelect={(next) => { onReview?.(); setPlaying(false); setPosition(clampPosition(next, results.length)); }} />

      <div className="mt-auto flex flex-wrap items-center gap-3 border-t pt-3" style={{ borderColor: "var(--color-line-subtle)" }}>
        {showPlayback && (
          <button
            onClick={() => {
              onReview?.();
              if (atEnd) setPosition(0);
              setPlaying(!playing || atEnd);
            }}
            disabled={results.length < 2}
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
          onChange={(event) => { onReview?.(); setPlaying(false); setPosition(clampPosition(Number(event.target.value), results.length)); }}
          className="min-w-[160px] flex-1 accent-[var(--color-accent)]"
          aria-label="Replay period"
        />
        {onLatest && <button onClick={onLatest} aria-pressed={followingLatest} title="Follow the latest recorded observation" className="inline-flex items-center gap-1.5 rounded px-2 py-1 text-[11px]" style={{ color: followingLatest ? "var(--color-supported)" : "var(--color-ink-dim)", border: "1px solid var(--color-line)" }}><Icon name="signal" size={12} />Latest</button>}
        <span className="tnum inline-flex items-center gap-1.5 text-[11px]" style={{ color: "var(--color-muted)" }}><Icon name="clock" size={12} />{dateTimeUTC(current.timestamp)} · {index + 1}/{results.length}</span>
      </div>
    </Panel>
  );
}

function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return <span className="inline-flex items-center gap-1.5"><i className="inline-block w-4" style={{ height: dashed ? 0 : 2, background: dashed ? undefined : color, borderTop: dashed ? `1px dashed ${color}` : undefined }} />{label}</span>;
}
