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
import { timeUTC } from "../lib/format";

// Time-series: the confidence range as a band, fair value + reference-under-test
// as lines. Y-domain is fitted tightly to the data so the (small) divergence is
// actually visible — a naive 0-based axis would flatten everything.
export function EscalationChart({
  results,
  index,
  onSelect,
}: {
  results: ValuationResult[];
  index: number;
  onSelect: (i: number) => void;
}) {
  const data = results.map((r, i) => ({
    i,
    t: timeUTC(r.timestamp).replace(" UTC", ""),
    band: [r.fair_value_lower, r.fair_value_upper] as [number, number],
    fair: r.valtide_fair_value,
    rut: r.reference_under_test,
  }));

  const lows = data.flatMap((d) => [d.band[0], d.rut].filter((v): v is number => v != null));
  const highs = data.flatMap((d) => [d.band[1], d.rut].filter((v): v is number => v != null));
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const pad = Math.max(0.1, (max - min) * 0.25);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <ComposedChart
          data={data}
          margin={{ top: 8, right: 16, bottom: 0, left: 4 }}
          onClick={(e) => {
            const idx = e?.activeTooltipIndex;
            if (typeof idx === "number") onSelect(idx);
          }}
        >
          <XAxis dataKey="t" stroke="var(--color-muted)" fontSize={12} tickLine={false} axisLine={{ stroke: "var(--color-line)" }} />
          <YAxis
            domain={[min - pad, max + pad]}
            stroke="var(--color-muted)"
            fontSize={12}
            tickLine={false}
            axisLine={false}
            width={52}
            tickFormatter={(v: number) => `$${v.toFixed(1)}`}
          />
          <Tooltip
            contentStyle={{ background: "#fff", border: "1px solid var(--color-line)", borderRadius: 10, fontSize: 13 }}
            labelStyle={{ color: "var(--color-ink-dim)" }}
            formatter={(v, name) => {
              if (name === "90% range" && Array.isArray(v)) return [`$${Number(v[0]).toFixed(2)} – $${Number(v[1]).toFixed(2)}`, name];
              return v == null ? ["—", name] : [`$${Number(v).toFixed(2)}`, name];
            }}
          />
          <Area
            dataKey="band"
            stroke="var(--color-supported-line)"
            fill="var(--color-supported-soft)"
            isAnimationActive={false}
            name="90% range"
          />
          <Line dataKey="fair" stroke="var(--color-supported)" strokeWidth={2.5} dot={false} name="Fair value" />
          <Line
            dataKey="rut"
            stroke="var(--color-challenged)"
            strokeWidth={2.5}
            strokeDasharray="5 4"
            dot={{ r: 3, fill: "var(--color-challenged)" }}
            name="Reference under test"
          />
          <ReferenceLine x={data[index]?.t} stroke="var(--color-ink-dim)" strokeDasharray="2 2" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
