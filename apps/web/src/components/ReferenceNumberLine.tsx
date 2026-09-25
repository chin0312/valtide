import type { ValuationResult } from "../api/types";
import { EVIDENCE } from "../lib/evidence";
import { money } from "../lib/format";
import { priceToFraction, unitsToFraction } from "../lib/scale";

export function ReferenceNumberLine({ r }: { r: ValuationResult }) {
  const candidates = [
    { label: "Reference", price: r.reference_under_test, color: EVIDENCE[r.evidence_state].fg, shape: "diamond" },
    { label: "Token market", price: r.token_price, color: "var(--color-series-token)", shape: "circle" },
    { label: "Last trusted", price: r.last_trusted_reference, color: "var(--color-series-trusted)", shape: "square" },
    { label: "Constructed", price: r.external_constructed_reference, color: "var(--color-series-valtide)", shape: "circle" },
  ];
  const markers = candidates.filter((marker): marker is typeof marker & { price: number } => marker.price != null);
  const bandStart = unitsToFraction(-1) * 100;
  const bandWidth = (unitsToFraction(1) - unitsToFraction(-1)) * 100;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
        <span className="tnum text-xl font-medium tracking-tight text-ink">{money(r.fair_value_lower)} – {money(r.fair_value_upper)}</span>
        <span className="text-[11px]" style={{ color: "var(--color-series-valtide)" }}>{Math.round(r.interval_coverage_target * 100)}% interval</span>
      </div>

      <div className="relative mx-2 h-[130px]" role="img" aria-label={`Fair value ${money(r.valtide_fair_value)}, interval ${money(r.fair_value_lower)} to ${money(r.fair_value_upper)}`}>
        <div className="absolute inset-x-0 top-[60px] h-px" style={{ background: "var(--color-line-strong)" }} />
        <div className="absolute top-[38px] h-11 rounded" style={{ left: `${bandStart}%`, width: `${bandWidth}%`, background: "var(--color-band-fill)", border: "1px solid var(--color-series-valtide)" }} />
        <div className="absolute left-1/2 top-[32px] h-14 w-px" style={{ background: "var(--color-series-valtide)" }} />
        <div className="absolute inset-x-0 top-0 text-center text-[11px]" style={{ color: "var(--color-muted)" }}>Fair value <span className="tnum ml-1 text-ink">{money(r.valtide_fair_value)}</span></div>
        {markers.map((marker, i) => (
          <div key={marker.label} className="absolute" style={{ left: `${priceToFraction(marker.price, r) * 100}%`, top: 46 + i * 14 }} title={`${marker.label}: ${money(marker.price)}`}>
            <span className="absolute h-2.5 w-2.5 -translate-x-1/2" style={{ background: marker.color, border: "1px solid var(--color-panel)", borderRadius: marker.shape === "circle" ? "50%" : 1, rotate: marker.shape === "diamond" ? "45deg" : undefined }} />
          </div>
        ))}
        <div className="absolute inset-x-0 bottom-0 flex justify-between text-[10px]" style={{ color: "var(--color-muted)" }}><span>Below range</span><span>Above range</span></div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3 border-t pt-4" style={{ borderColor: "var(--color-line-subtle)" }}>
        {markers.map((marker) => <div key={marker.label} className="min-w-0"><div className="flex items-center gap-1.5 text-[10px]" style={{ color: "var(--color-muted)" }}><i className="h-1.5 w-1.5 shrink-0" style={{ background: marker.color, borderRadius: marker.shape === "circle" ? "50%" : 1, rotate: marker.shape === "diamond" ? "45deg" : undefined }} />{marker.label}</div><div className="tnum mt-1 text-sm font-medium text-ink">{money(marker.price)}</div></div>)}
      </div>
    </div>
  );
}
