import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ValuationResult } from "../api/types";
import { coverageLabel, dateTimeUTC, timeAxisUTC } from "../lib/format";

interface ChartPoint {
  sourceIndex: number | null;
  ts: number;
  band: [number, number] | null;
  fair: number | null;
  rut: number | null;
  token: number | null;
}

const CANONICAL_STEP_MS = 5 * 60 * 1000;

// Time-series: the calibrated interval as a band, fair value + references as
// lines. X is a real UTC timestamp, not a repeated HH:MM category. Null gap
// sentinels are chart-only and make scheduler gaps visually explicit without
// inventing observations or selectable rows.
export function EscalationChart({
  results,
  index,
  onSelect,
}: {
  results: ValuationResult[];
  index: number;
  onSelect: (i: number) => void;
}) {
  const data = buildChartData(results);
  const realPoints = data.filter((point) => point.sourceIndex != null);
  const timestamps = realPoints.map((point) => point.ts);
  const minTimestamp = Math.min(...timestamps);
  const maxTimestamp = Math.max(...timestamps);
  const multiDay = new Date(minTimestamp).toISOString().slice(0, 10) !== new Date(maxTimestamp).toISOString().slice(0, 10);
  const coverageTargets = [...new Set(results.map((result) => result.interval_coverage_target))];
  const intervalName = coverageTargets.length === 1 ? coverageLabel(coverageTargets[0]) : "Calibrated interval";
  const lows = data.flatMap((point) => [point.band?.[0], point.rut, point.token].filter((value): value is number => value != null));
  const highs = data.flatMap((point) => [point.band?.[1], point.rut, point.token].filter((value): value is number => value != null));
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const pad = Math.max(0.1, (max - min) * 0.25);
  const selectedPoint = data.find((point) => point.sourceIndex === index);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <ComposedChart
          data={data}
          margin={{ top: 8, right: 16, bottom: 0, left: 4 }}
          onClick={(event) => {
            const activeIndex = event?.activeTooltipIndex;
            const sourceIndex = typeof activeIndex === "number" ? data[activeIndex]?.sourceIndex : null;
            if (sourceIndex != null) onSelect(sourceIndex);
          }}
        >
          <XAxis
            type="number"
            dataKey="ts"
            domain={[minTimestamp, maxTimestamp]}
            tickFormatter={(value: number) => timeAxisUTC(Number(value), multiDay)}
            stroke="var(--color-muted)"
            fontSize={12}
            tickLine={false}
            axisLine={{ stroke: "var(--color-line)" }}
          />
          <YAxis
            domain={[min - pad, max + pad]}
            stroke="var(--color-muted)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            width={52}
            tickFormatter={(value: number) => `$${value.toFixed(1)}`}
          />
          <Tooltip
            contentStyle={{ background: "#fff", border: "1px solid var(--color-line)", borderRadius: 10, fontSize: 13 }}
            labelStyle={{ color: "var(--color-ink-dim)" }}
            labelFormatter={(label) => dateTimeUTC(new Date(Number(label)).toISOString())}
            formatter={(value, name) => {
              if (name === intervalName && Array.isArray(value)) return [`$${Number(value[0]).toFixed(2)} – $${Number(value[1]).toFixed(2)}`, name];
              return value == null ? ["—", name] : [`$${Number(value).toFixed(2)}`, name];
            }}
          />
          <Area
            dataKey="band"
            stroke="var(--color-supported-line)"
            fill="var(--color-supported-soft)"
            connectNulls={false}
            isAnimationActive={false}
            name={intervalName}
          />
          <Line dataKey="fair" stroke="var(--color-supported)" strokeWidth={2.5} dot={false} connectNulls={false} name="Fair value" />
          <Line
            dataKey="rut"
            stroke="var(--color-challenged)"
            strokeWidth={2.5}
            strokeDasharray="5 4"
            dot={{ r: 3, fill: "var(--color-challenged)" }}
            connectNulls={false}
            name="Reference under test"
          />
          <Line
            dataKey="token"
            stroke="var(--color-token)"
            strokeWidth={1.5}
            dot={false}
            connectNulls={false}
            name="Tokenized market"
          />
          <ReferenceLine x={selectedPoint?.ts} stroke="var(--color-ink-dim)" strokeDasharray="2 2" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function buildChartData(results: ValuationResult[]): ChartPoint[] {
  const points: ChartPoint[] = [];
  let previousTimestamp: number | null = null;

  results.forEach((result, sourceIndex) => {
    const timestamp = Date.parse(result.timestamp);
    if (!Number.isFinite(timestamp)) return;

    if (previousTimestamp != null && timestamp - previousTimestamp > CANONICAL_STEP_MS) {
      points.push({ sourceIndex: null, ts: previousTimestamp + Math.floor((timestamp - previousTimestamp) / 2), band: null, fair: null, rut: null, token: null });
    }

    points.push({
      sourceIndex,
      ts: timestamp,
      band: [result.fair_value_lower, result.fair_value_upper],
      fair: result.valtide_fair_value,
      rut: result.reference_under_test,
      token: result.token_price,
    });
    previousTimestamp = timestamp;
  });

  return points;
}
