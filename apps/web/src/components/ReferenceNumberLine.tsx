import type { ValuationResult } from "../api/types";
import { EVIDENCE } from "../lib/evidence";
import { coverageLabel, money } from "../lib/format";
import { AXIS_MAX, AXIS_MIN, toBandUnits, unitsToFraction } from "../lib/scale";

interface Marker {
  key: string;
  label: string;
  price: number;
  color: string;
  topPct: number;
}

export function ReferenceNumberLine({ r }: { r: ValuationResult }) {
  const candidates: Array<Omit<Marker, "topPct"> | null> = [
    r.reference_under_test == null ? null : { key: "rut", label: "Reference", price: r.reference_under_test, color: EVIDENCE[r.evidence_state].fg },
    r.token_price == null ? null : { key: "token", label: "Token market", price: r.token_price, color: "var(--color-series-token)" },
    { key: "trusted", label: "Last trusted", price: r.last_trusted_reference, color: "var(--color-series-trusted)" },
    r.external_constructed_reference == null ? null : { key: "ext", label: "Constructed", price: r.external_constructed_reference, color: "var(--color-series-valtide)" },
  ];
  const markers = candidates
    .filter((marker): marker is Omit<Marker, "topPct"> => marker != null)
    .map((marker) => ({ ...marker, topPct: 100 - unitsToFraction(toBandUnits(marker.price, r)) * 100 }));
  const bandTop = 100 - unitsToFraction(1) * 100;
  const bandBottom = 100 - unitsToFraction(-1) * 100;
  const fairTop = 100 - unitsToFraction(0) * 100;

  return (
    <div className="grid min-h-[410px] grid-cols-[78px_minmax(0,1fr)] gap-5">
      <div className="relative my-4 ml-2">
        <div className="absolute left-[34px] top-0 h-full w-px" style={{ background: "var(--color-line-strong)" }} />
        <div className="absolute left-[22px] w-6 rounded-sm" style={{ top: `${bandTop}%`, height: `${bandBottom - bandTop}%`, background: "var(--color-band-fill)", border: "1px solid var(--color-series-valtide)" }} title={coverageLabel(r.interval_coverage_target)} />
        <div className="absolute left-[16px] h-px w-9" style={{ top: `${fairTop}%`, background: "var(--color-series-valtide)" }} />
        <AxisTick top={0} value={money(priceAtUnits(AXIS_MAX, r))} />
        <AxisTick top={bandTop} value={money(r.fair_value_upper)} accent />
        <AxisTick top={fairTop} value={money(r.valtide_fair_value)} accent />
        <AxisTick top={bandBottom} value={money(r.fair_value_lower)} accent />
        <AxisTick top={100} value={money(priceAtUnits(AXIS_MIN, r))} />
        {markers.map((marker, index) => <MarkerDot key={marker.key} marker={marker} offset={index} />)}
      </div>

      <div className="flex flex-col justify-between py-4">
        <div>
          <div className="eyebrow" style={{ color: "var(--color-muted)" }}>Calibrated range</div>
          <div className="tnum mt-2 text-lg font-medium text-ink">{money(r.fair_value_lower)}–{money(r.fair_value_upper)}</div>
          <span className="mt-2 inline-flex rounded px-2 py-1 font-mono text-[9px] uppercase tracking-[0.04em]" style={{ color: "var(--color-series-valtide)", background: "var(--color-band-fill)" }}>{coverageLabel(r.interval_coverage_target)}</span>
        </div>
        <div className="space-y-3">
          {markers.map((marker) => (
            <div key={marker.key} className="flex items-start gap-2.5">
              <i className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: marker.color }} />
              <div className="min-w-0"><div className="text-[10px]" style={{ color: "var(--color-muted)" }}>{marker.label}</div><div className="tnum text-xs font-medium text-ink">{money(marker.price)}</div></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AxisTick({ top, value, accent }: { top: number; value: string; accent?: boolean }) {
  return <div className="absolute left-0 -translate-y-1/2" style={{ top: `${top}%` }}><span className="tnum text-[8px]" style={{ color: accent ? "var(--color-series-valtide)" : "var(--color-muted)" }}>{value}</span></div>;
}

function MarkerDot({ marker, offset }: { marker: Marker; offset: number }) {
  const left = 30 + (offset % 2) * 12;
  return <div className="absolute h-3 w-3 -translate-y-1/2 rotate-45" style={{ left, top: `${marker.topPct}%`, background: marker.color, border: "2px solid var(--color-panel)", boxShadow: "0 0 0 1px var(--color-line-strong)" }} title={`${marker.label}: ${money(marker.price)}`} />;
}

function priceAtUnits(units: number, r: ValuationResult): number {
  return units < 0 ? r.valtide_fair_value + units * (r.valtide_fair_value - r.fair_value_lower) : r.valtide_fair_value + units * (r.fair_value_upper - r.valtide_fair_value);
}
