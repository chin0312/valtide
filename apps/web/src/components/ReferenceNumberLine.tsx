import type { ValuationResult } from "../api/types";
import { EVIDENCE } from "../lib/evidence";
import { coverageLabel, money } from "../lib/format";
import { AXIS_MAX, AXIS_MIN, toBandUnits, unitsToFraction } from "../lib/scale";

interface Marker {
  key: string;
  label: string;
  price: number;
  color: string;
  leftPct: number;
  emphasize?: boolean;
}

export function ReferenceNumberLine({ r }: { r: ValuationResult }) {
  const rawMarkers: Array<Omit<Marker, "leftPct"> | null> = [
    r.reference_under_test == null ? null : { key: "rut", label: "Reference under test", price: r.reference_under_test, emphasize: true, color: EVIDENCE[r.evidence_state].fg },
    r.token_price == null ? null : { key: "token", label: "Tokenized market", price: r.token_price, color: "var(--color-series-token)" },
    { key: "trusted", label: "Last trusted price", price: r.last_trusted_reference, color: "var(--color-series-trusted)" },
    r.external_constructed_reference == null ? null : { key: "ext", label: "Constructed reference", price: r.external_constructed_reference, color: "var(--color-series-valtide)" },
  ];
  const markers: Marker[] = rawMarkers.filter((marker): marker is Omit<Marker, "leftPct"> => marker != null).map((marker) => ({ ...marker, leftPct: unitsToFraction(toBandUnits(marker.price, r)) * 100 }));

  const clusters = clusterMarkers(markers);
  const bandL = unitsToFraction(-1) * 100;
  const bandR = unitsToFraction(1) * 100;
  const axisY = 112;

  return (
    <div className="w-full overflow-hidden">
      <div className="relative mx-4 h-[230px] select-none sm:mx-10">
        <div className="absolute rounded" style={{ left: `${bandL}%`, width: `${bandR - bandL}%`, top: axisY - 20, height: 40, background: "var(--color-band-fill)", border: "1px solid var(--color-series-valtide)" }} />
        <div className="absolute left-0 right-0 h-px" style={{ top: axisY, background: "var(--color-line-strong)" }} />
        <Boundary leftPct={bandL} axisY={axisY} label={money(r.fair_value_lower)} />
        <Boundary leftPct={bandR} axisY={axisY} label={money(r.fair_value_upper)} />
        <AxisLabel leftPct={0} axisY={axisY} value={money(priceAtUnits(AXIS_MIN, r))} align="left" />
        <AxisLabel leftPct={50} axisY={axisY} value={`${money(r.valtide_fair_value)} fair value`} align="center" />
        <AxisLabel leftPct={100} axisY={axisY} value={money(priceAtUnits(AXIS_MAX, r))} align="right" />

        {clusters.map((cluster, clusterIndex) => <MarkerCluster key={cluster.map((m) => m.key).join("-")} markers={cluster} axisY={axisY} above={cluster.some((m) => m.key === "rut" || m.key === "token") || clusterIndex % 2 === 0} />)}
      </div>
      <p className="text-center text-[11px]" style={{ color: "var(--color-muted)" }}>Shaded band = Valtide's {coverageLabel(r.interval_coverage_target)}. Coincident sources share one marker stack.</p>
    </div>
  );
}

function clusterMarkers(markers: Marker[]): Marker[][] {
  const sorted = [...markers].sort((a, b) => a.leftPct - b.leftPct);
  const clusters: Marker[][] = [];
  sorted.forEach((marker) => {
    const current = clusters[clusters.length - 1];
    const anchor = current ? current.reduce((sum, item) => sum + item.leftPct, 0) / current.length : 0;
    if (current && Math.abs(marker.leftPct - anchor) <= 4) current.push(marker);
    else clusters.push([marker]);
  });
  return clusters;
}

function MarkerCluster({ markers, axisY, above }: { markers: Marker[]; axisY: number; above: boolean }) {
  const leftPct = markers.reduce((sum, marker) => sum + marker.leftPct, 0) / markers.length;
  const labelHeight = markers.length * 34;
  const labelY = above ? axisY - labelHeight - 30 : axisY + 30;
  return (
    <div className="absolute top-0" style={{ left: `${leftPct}%`, transform: "translateX(-50%)" }}>
      <div className="absolute w-px" style={{ left: "50%", top: above ? labelY + labelHeight : axisY, height: above ? axisY - labelY - labelHeight : labelY - axisY, background: "var(--color-line-strong)" }} />
      <div className="absolute rounded-full" style={{ left: "50%", top: axisY, transform: "translate(-50%,-50%)", width: 13, height: 13, background: markers[0].color, border: "2px solid var(--color-panel)", boxShadow: markers.some((m) => m.emphasize) ? "0 0 0 3px var(--color-panel-3)" : "none", zIndex: 2 }} />
      <div className="absolute w-44" style={{ left: "50%", top: labelY, transform: "translateX(-50%)" }}>
        {markers.map((marker) => (
          <div key={marker.key} className="mb-1 text-center">
            <div className="text-[11px] font-medium" style={{ color: marker.color }}>{marker.label}</div>
            <div className="tnum text-[11px] text-ink">{money(marker.price)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Boundary({ leftPct, axisY, label }: { leftPct: number; axisY: number; label: string }) {
  return <div className="absolute" style={{ left: `${leftPct}%`, top: axisY - 27, transform: "translateX(-50%)" }}><div className="mx-auto h-[54px] w-px" style={{ background: "var(--color-series-valtide)" }} /><div className="tnum mt-1 whitespace-nowrap text-[10px]" style={{ color: "var(--color-series-valtide)" }}>{label}</div></div>;
}

function AxisLabel({ leftPct, axisY, value, align }: { leftPct: number; axisY: number; value: string; align: "left" | "center" | "right" }) {
  const transform = align === "center" ? "translateX(-50%)" : align === "right" ? "translateX(-100%)" : undefined;
  return <div className="tnum absolute whitespace-nowrap text-[10px]" style={{ left: `${leftPct}%`, top: axisY + 42, transform, color: "var(--color-muted)" }}>{value}</div>;
}

function priceAtUnits(units: number, r: ValuationResult): number {
  return units < 0 ? r.valtide_fair_value + units * (r.valtide_fair_value - r.fair_value_lower) : r.valtide_fair_value + units * (r.fair_value_upper - r.valtide_fair_value);
}
