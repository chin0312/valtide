import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type WheelEvent as ReactWheelEvent } from "react";
import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EvidenceState, ValuationResult } from "../api/types";
import { EVIDENCE } from "../lib/evidence";
import { coverageLabel, dateTimeUTC, timeAxisUTC } from "../lib/format";

interface ChartPoint {
  sourceIndex: number | null;
  ts: number;
  band: [number, number] | null;
  fair: number | null;
  rut: number | null;
  token: number | null;
  state: EvidenceState | null;
}

interface DotProps {
  cx?: number;
  cy?: number;
  payload?: ChartPoint;
}

const CANONICAL_STEP_MS = 5 * 60 * 1000;
const MIN_VIEWPORT_STEPS = 2;
const DRAG_THRESHOLD_PX = 4;
const ZOOM_IN_SCALE = 0.8;
const ZOOM_OUT_SCALE = 1.25;
const CHART_MARGIN = { top: 10, right: 18, bottom: 4, left: 2 } as const;
const Y_AXIS_WIDTH = 50;

export type ChartDomain = [number, number];

export function chartDomain(timestamps: number[]): ChartDomain {
  const valid = [...new Set(timestamps.filter((timestamp) => Number.isFinite(timestamp)))].sort((a, b) => a - b);
  if (valid.length === 0) return [0, CANONICAL_STEP_MS];
  if (valid.length === 1) return [valid[0] - CANONICAL_STEP_MS / 2, valid[0] + CANONICAL_STEP_MS / 2];
  return [valid[0], valid[valid.length - 1]];
}

export function minimumViewportWidth(timestamps: number[]): number {
  const valid = [...new Set(timestamps.filter((timestamp) => Number.isFinite(timestamp)))].sort((a, b) => a - b);
  const gaps = valid.slice(1).map((timestamp, index) => timestamp - valid[index]).filter((gap) => gap > 0);
  return Math.max(CANONICAL_STEP_MS * MIN_VIEWPORT_STEPS, (gaps.length ? Math.min(...gaps) : CANONICAL_STEP_MS) * MIN_VIEWPORT_STEPS);
}

export function clampViewport(viewport: ChartDomain, fullDomain: ChartDomain, minimumWidth = CANONICAL_STEP_MS * MIN_VIEWPORT_STEPS): ChartDomain {
  const fullStart = Math.min(fullDomain[0], fullDomain[1]);
  const fullEnd = Math.max(fullDomain[0], fullDomain[1]);
  const fullWidth = fullEnd - fullStart;
  if (fullWidth <= 0) return [fullStart, fullEnd];

  const rawStart = Number.isFinite(viewport[0]) ? viewport[0] : fullStart;
  const rawEnd = Number.isFinite(viewport[1]) ? viewport[1] : fullEnd;
  const requestedStart = Math.min(rawStart, rawEnd);
  const requestedEnd = Math.max(rawStart, rawEnd);
  const width = Math.min(fullWidth, Math.max(minimumWidth, requestedEnd - requestedStart));
  if (width >= fullWidth) return [fullStart, fullEnd];

  let start = requestedStart;
  let end = start + width;
  if (start < fullStart) {
    start = fullStart;
    end = start + width;
  }
  if (end > fullEnd) {
    end = fullEnd;
    start = end - width;
  }
  return [start, end];
}

export function zoomViewport(viewport: ChartDomain, fullDomain: ChartDomain, anchorTimestamp: number, scale: number, minimumWidth = CANONICAL_STEP_MS * MIN_VIEWPORT_STEPS): ChartDomain {
  const current = clampViewport(viewport, fullDomain, minimumWidth);
  const currentWidth = current[1] - current[0];
  const fullWidth = Math.abs(fullDomain[1] - fullDomain[0]);
  if (currentWidth <= 0 || fullWidth <= 0 || !Number.isFinite(scale) || scale <= 0) return current;

  const anchor = Math.min(current[1], Math.max(current[0], Number.isFinite(anchorTimestamp) ? anchorTimestamp : current[0] + currentWidth / 2));
  const anchorRatio = (anchor - current[0]) / currentWidth;
  const nextWidth = Math.min(fullWidth, Math.max(minimumWidth, currentWidth * scale));
  return clampViewport([anchor - nextWidth * anchorRatio, anchor + nextWidth * (1 - anchorRatio)], fullDomain, minimumWidth);
}

export function panViewport(viewport: ChartDomain, fullDomain: ChartDomain, deltaMs: number, minimumWidth = CANONICAL_STEP_MS * MIN_VIEWPORT_STEPS): ChartDomain {
  const current = clampViewport(viewport, fullDomain, minimumWidth);
  if (!Number.isFinite(deltaMs)) return current;
  return clampViewport([current[0] + deltaMs, current[1] + deltaMs], fullDomain, minimumWidth);
}

export function EscalationChart({ results, index, playhead = index, onSelect, resetKey }: { results: ValuationResult[]; index: number; playhead?: number; onSelect: (i: number) => void; resetKey?: string | number }) {
  const data = buildChartData(results);
  const realPoints = data.filter((point) => point.sourceIndex != null);
  const timestamps = realPoints.map((point) => point.ts);
  const fullDomain = chartDomain(timestamps);
  const minimumWidth = minimumViewportWidth(timestamps);
  const [viewport, setViewport] = useState<ChartDomain>(fullDomain);
  const [panning, setPanning] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ pointerId: number; startX: number; startDomain: ChartDomain; moved: boolean } | null>(null);

  useEffect(() => {
    setViewport(fullDomain);
  }, [fullDomain[0], fullDomain[1], resetKey]);

  const viewportDomain = clampViewport(viewport, fullDomain, minimumWidth);
  const visibleData = data.filter((point) => point.ts >= viewportDomain[0] && point.ts <= viewportDomain[1]);
  const allPrices = data.flatMap((point) => [point.band?.[0], point.band?.[1], point.rut, point.token].filter((value): value is number => value != null));
  const visiblePrices = visibleData.flatMap((point) => [point.band?.[0], point.band?.[1], point.rut, point.token].filter((value): value is number => value != null));
  const prices = visiblePrices.length ? visiblePrices : allPrices;
  const minTimestamp = viewportDomain[0];
  const maxTimestamp = viewportDomain[1];
  const multiDay = new Date(minTimestamp).toISOString().slice(0, 10) !== new Date(maxTimestamp).toISOString().slice(0, 10);
  const coverageTargets = [...new Set(results.map((result) => result.interval_coverage_target))];
  const intervalName = coverageTargets.length === 1 ? coverageLabel(coverageTargets[0]) : "Calibrated interval";
  const min = prices.length ? Math.min(...prices) : 0;
  const max = prices.length ? Math.max(...prices) : 1;
  const span = max - min;
  const pad = Math.max(0.1, span * 0.2);
  const cursorTimestamp = timestampAtPosition(results, playhead);
  const yDecimals = span < 2 ? 1 : 0;

  const plotRatioAt = (clientX: number): number => {
    const rect = chartRef.current?.getBoundingClientRect();
    if (!rect) return 0.5;
    const plotLeft = CHART_MARGIN.left + Y_AXIS_WIDTH;
    const plotWidth = Math.max(1, rect.width - plotLeft - CHART_MARGIN.right);
    return Math.min(1, Math.max(0, (clientX - rect.left - plotLeft) / plotWidth));
  };

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    if (event.deltaY === 0) return;
    event.preventDefault();
    const ratio = plotRatioAt(event.clientX);
    const scale = event.deltaY < 0 ? ZOOM_IN_SCALE : ZOOM_OUT_SCALE;
    setViewport((current) => {
      const safe = clampViewport(current, fullDomain, minimumWidth);
      const anchor = safe[0] + (safe[1] - safe[0]) * ratio;
      return zoomViewport(safe, fullDomain, anchor, scale, minimumWidth);
    });
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    dragRef.current = { pointerId: event.pointerId, startX: event.clientX, startDomain: viewportDomain, moved: false };
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - drag.startX;
    if (!drag.moved && Math.abs(deltaX) < DRAG_THRESHOLD_PX) return;
    drag.moved = true;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setPanning(true);
    const rect = chartRef.current?.getBoundingClientRect();
    if (!rect) return;
    const plotLeft = CHART_MARGIN.left + Y_AXIS_WIDTH;
    const plotWidth = Math.max(1, rect.width - plotLeft - CHART_MARGIN.right);
    const deltaMs = -(deltaX / plotWidth) * (drag.startDomain[1] - drag.startDomain[0]);
    setViewport(panViewport(drag.startDomain, fullDomain, deltaMs, minimumWidth));
  };

  const finishPointer = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    dragRef.current = null;
    setPanning(false);
    if (!drag.moved) {
      const ratio = plotRatioAt(event.clientX);
      const timestamp = viewportDomain[0] + (viewportDomain[1] - viewportDomain[0]) * ratio;
      const nearest = realPoints.reduce<ChartPoint | null>((candidate, point) => {
        if (candidate == null || Math.abs(point.ts - timestamp) < Math.abs(candidate.ts - timestamp)) return point;
        return candidate;
      }, null);
      if (nearest?.sourceIndex != null) onSelect(nearest.sourceIndex);
    }
  };

  return (
    <div
      ref={chartRef}
      className="h-[320px] min-h-[280px] w-full flex-1"
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={finishPointer}
      onPointerCancel={finishPointer}
      aria-label="Interactive valuation chart"
      style={{ cursor: panning ? "grabbing" : "grab", touchAction: "none", userSelect: "none" }}
    >
      <ResponsiveContainer>
        <ComposedChart
          data={data}
          margin={CHART_MARGIN}
        >
          <XAxis type="number" dataKey="ts" domain={viewportDomain} tickFormatter={(value: number) => timeAxisUTC(Number(value), multiDay)} stroke="var(--color-muted)" fontFamily="Inter" fontSize={10} tickLine={false} axisLine={{ stroke: "var(--color-line)" }} minTickGap={42} />
          <YAxis domain={[min - pad, max + pad]} stroke="var(--color-muted)" fontFamily="Inter" fontSize={10} tickLine={false} axisLine={false} width={50} tickFormatter={(value: number) => `$${value.toFixed(yDecimals)}`} />
          <Tooltip
            contentStyle={{ background: "#111718", border: "1px solid #253237", borderRadius: 8, fontSize: 11, color: "#f3faf7", fontFamily: "Inter" }}
            labelStyle={{ color: "#b8c7c2", marginBottom: 6 }}
            labelFormatter={(label) => dateTimeUTC(new Date(Number(label)).toISOString())}
            formatter={(value, name) => {
              if (name === intervalName && Array.isArray(value)) return [`$${Number(value[0]).toFixed(2)} – $${Number(value[1]).toFixed(2)}`, name];
              return value == null ? ["—", name] : [`$${Number(value).toFixed(2)}`, name];
            }}
          />
          <Area dataKey="band" stroke="var(--color-series-valtide)" strokeWidth={1} fill="var(--color-band-fill)" connectNulls={false} isAnimationActive={false} name={intervalName} />
          <Line dataKey="fair" stroke="var(--color-series-valtide)" strokeWidth={1.75} dot={false} connectNulls={false} isAnimationActive={false} name="Fair value" />
          <Line
            dataKey="rut"
            stroke="var(--color-series-reference)"
            strokeWidth={1.5}
            strokeDasharray="5 4"
            dot={(props: DotProps & { key?: string | number }) => {
              const { key, ...dotProps } = props;
              return <StateDot key={key} {...dotProps} selectedIndex={index} />;
            }}
            activeDot={false}
            connectNulls={false}
            isAnimationActive={false}
            name="Reference under test"
          />
          <Line dataKey="token" stroke="var(--color-series-token)" strokeWidth={1.25} strokeOpacity={0.72} dot={false} connectNulls={false} isAnimationActive={false} name="Tokenized market" />
          <ReferenceLine x={cursorTimestamp} stroke="var(--color-accent)" strokeOpacity={0.65} strokeDasharray="2 3" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function timestampAtPosition(results: ValuationResult[], position: number): number | undefined {
  if (!results.length) return undefined;
  const lowerIndex = Math.max(0, Math.min(Math.floor(position), results.length - 1));
  const upperIndex = Math.min(lowerIndex + 1, results.length - 1);
  const lower = Date.parse(results[lowerIndex].timestamp);
  const upper = Date.parse(results[upperIndex].timestamp);
  if (!Number.isFinite(lower) || !Number.isFinite(upper)) return undefined;
  return lower + (upper - lower) * (position - lowerIndex);
}

function StateDot({ cx, cy, payload, selectedIndex }: DotProps & { selectedIndex: number }) {
  if (cx == null || cy == null || !payload?.state || payload.sourceIndex == null) return <g />;
  const color = EVIDENCE[payload.state].fg;
  const selected = payload.sourceIndex === selectedIndex;
  const size = selected ? 5 : 3.5;

  if (payload.state === "SUPPORTED") return <rect x={cx - size} y={cy - size} width={size * 2} height={size * 2} rx={1} fill={color} stroke="var(--color-panel)" strokeWidth={1.5} />;
  if (payload.state === "INCONCLUSIVE") return <path d={`M ${cx} ${cy - size - 1} L ${cx + size + 1} ${cy} L ${cx} ${cy + size + 1} L ${cx - size - 1} ${cy} Z`} fill={color} stroke="var(--color-panel)" strokeWidth={1.5} />;
  return (
    <g stroke={color} strokeWidth={selected ? 2.5 : 2} strokeLinecap="square">
      <line x1={cx - size} y1={cy - size} x2={cx + size} y2={cy + size} />
      <line x1={cx + size} y1={cy - size} x2={cx - size} y2={cy + size} />
    </g>
  );
}

function buildChartData(results: ValuationResult[]): ChartPoint[] {
  const points: ChartPoint[] = [];
  let previousTimestamp: number | null = null;

  results.forEach((result, sourceIndex) => {
    const timestamp = Date.parse(result.timestamp);
    if (!Number.isFinite(timestamp)) return;
    if (previousTimestamp != null && timestamp - previousTimestamp > CANONICAL_STEP_MS) {
      points.push({ sourceIndex: null, ts: previousTimestamp + Math.floor((timestamp - previousTimestamp) / 2), band: null, fair: null, rut: null, token: null, state: null });
    }
    points.push({ sourceIndex, ts: timestamp, band: [result.fair_value_lower, result.fair_value_upper], fair: result.valtide_fair_value, rut: result.reference_under_test, token: result.token_price, state: result.evidence_state });
    previousTimestamp = timestamp;
  });
  return points;
}
