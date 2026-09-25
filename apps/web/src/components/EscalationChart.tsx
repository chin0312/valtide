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

export function EscalationChart({ results, index, playhead = index, onSelect }: { results: ValuationResult[]; index: number; playhead?: number; onSelect: (i: number) => void }) {
  const data = buildChartData(results);
  const realPoints = data.filter((point) => point.sourceIndex != null);
  const timestamps = realPoints.map((point) => point.ts);
  const minTimestamp = Math.min(...timestamps);
  const maxTimestamp = Math.max(...timestamps);
  const multiDay = new Date(minTimestamp).toISOString().slice(0, 10) !== new Date(maxTimestamp).toISOString().slice(0, 10);
  const coverageTargets = [...new Set(results.map((result) => result.interval_coverage_target))];
  const intervalName = coverageTargets.length === 1 ? coverageLabel(coverageTargets[0]) : "Calibrated interval";
  const prices = data.flatMap((point) => [point.band?.[0], point.band?.[1], point.rut, point.token].filter((value): value is number => value != null));
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min;
  const pad = Math.max(0.1, span * 0.2);
  const cursorTimestamp = timestampAtPosition(results, playhead);
  const yDecimals = span < 2 ? 1 : 0;

  return (
    <div className="h-[320px] min-h-[280px] w-full flex-1">
      <ResponsiveContainer>
        <ComposedChart
          data={data}
          margin={{ top: 10, right: 18, bottom: 4, left: 2 }}
          onClick={(event) => {
            const activeIndex = event?.activeTooltipIndex;
            const sourceIndex = typeof activeIndex === "number" ? data[activeIndex]?.sourceIndex : null;
            if (sourceIndex != null) onSelect(sourceIndex);
          }}
        >
          <XAxis type="number" dataKey="ts" domain={[minTimestamp, maxTimestamp]} tickFormatter={(value: number) => timeAxisUTC(Number(value), multiDay)} stroke="var(--color-muted)" fontFamily="Inter" fontSize={10} tickLine={false} axisLine={{ stroke: "var(--color-line)" }} minTickGap={42} />
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
