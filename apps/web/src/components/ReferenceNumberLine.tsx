import type { ValuationResult } from "../api/types";
import { coverageLabel, money } from "../lib/format";
import { priceToFraction, rangeViewPriceDomain, rangeViewXperpPrice } from "../lib/scale";
import { isXStockValidation } from "../lib/semantics";

const displayMoney = (price: number | null | undefined) => money(Number.isFinite(price) ? price : null);

export function ReferenceNumberLine({ r, domainResults = [r] }: { r: ValuationResult; domainResults?: ValuationResult[] }) {
  const xstockProduct = isXStockValidation(r);
  const xperpPrice = rangeViewXperpPrice(r);
  const domain = rangeViewPriceDomain(domainResults);
  const fairValueFraction = priceToFraction(r.valtide_fair_value, domain);
  const xstockPrices = [
    { label: "Observed xStock", price: r.token_price, color: "var(--color-series-token)", shape: "circle" },
    { label: "Valtide Fair Value", price: r.valtide_fair_value, color: "var(--color-series-valtide)", shape: "square" },
    { label: "X-Perp", price: xperpPrice, color: "var(--color-series-reference)", shape: "diamond" },
  ];
  const candidates = [
    ...(xstockProduct ? xstockPrices : [
      { label: "Reference under test", price: r.reference_under_test, color: "var(--color-series-reference)", shape: "diamond" },
    ]),
  ];
  const markers = candidates.filter((marker): marker is typeof marker & { price: number } => marker.price != null && Number.isFinite(marker.price));
  const summary = xstockProduct ? xstockPrices : markers;
  const validInterval = Number.isFinite(r.fair_value_lower)
    && Number.isFinite(r.fair_value_upper)
    && r.fair_value_upper > r.fair_value_lower;
  const bandStart = validInterval ? priceToFraction(r.fair_value_lower, domain) * 100 : fairValueFraction * 100;
  const bandEnd = validInterval ? priceToFraction(r.fair_value_upper, domain) * 100 : bandStart;
  const bandWidth = validInterval ? Math.max(0, bandEnd - bandStart) : 0;
  const rangeLabel = coverageLabel(r.interval_coverage_target);
  const accessibleLabel = xstockProduct
    ? `Observed xStock ${displayMoney(r.token_price)}; Valtide Fair Value ${displayMoney(r.valtide_fair_value)}; X-Perp ${displayMoney(xperpPrice)}; ${rangeLabel} from ${displayMoney(r.fair_value_lower)} to ${displayMoney(r.fair_value_upper)}`
    : `Reference under test ${displayMoney(r.reference_under_test)}; Valtide Fair Value ${displayMoney(r.valtide_fair_value)}; ${rangeLabel} from ${displayMoney(r.fair_value_lower)} to ${displayMoney(r.fair_value_upper)}`;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
        <span className="tnum text-xl font-medium tracking-tight text-ink">{displayMoney(r.fair_value_lower)} – {displayMoney(r.fair_value_upper)}</span>
        <span className="text-[11px]" style={{ color: "var(--color-series-valtide)" }}>{rangeLabel}</span>
      </div>

      <div className="relative mx-2 h-[130px]" role="img" aria-label={accessibleLabel} title={accessibleLabel}>
        <div className="absolute inset-x-0 top-[60px] h-px" style={{ background: "var(--color-line-strong)" }} />
        <div className="absolute top-[38px] h-11 rounded transition-[left,width] duration-200 ease-out" style={{ left: `${bandStart}%`, width: `${bandWidth}%`, background: "var(--color-band-fill)", border: "1px solid var(--color-series-valtide)" }} />
        <div className="absolute top-[32px] h-14 w-px transition-[left] duration-200 ease-out" style={{ left: `${fairValueFraction * 100}%`, background: "var(--color-series-valtide)" }} />
        <div className="absolute top-0 -translate-x-1/2 whitespace-nowrap text-center text-[11px] transition-[left] duration-200 ease-out" style={{ left: `${fairValueFraction * 100}%`, color: "var(--color-muted)" }}>Valtide Fair Value <span className="tnum ml-1 text-ink">{displayMoney(r.valtide_fair_value)}</span></div>
        {markers.map((marker) => {
          const markerFraction = priceToFraction(marker.price, domain);
          return <div key={marker.label} data-price-marker={marker.label} className="absolute transition-[left] duration-200 ease-out" style={{ left: `${markerFraction * 100}%`, top: 60, zIndex: marker.shape === "diamond" ? 3 : marker.shape === "square" ? 2 : 1 }} title={`${marker.label}: ${displayMoney(marker.price)}`}>
            <svg className="absolute -translate-x-1/2 -translate-y-1/2" width="28" height="28" viewBox="0 0 28 28" aria-hidden="true" style={{ overflow: "visible" }}>
              {/* Nested outlines keep equal-price sources visible at their exact position. */}
              {marker.shape === "diamond" ? <path d="M14 2 26 14 14 26 2 14Z" fill="none" stroke={marker.color} strokeWidth="2" />
                : marker.shape === "square" ? <rect x="7" y="7" width="14" height="14" rx="1" fill="none" stroke={marker.color} strokeWidth="2" />
                  : <circle cx="14" cy="14" r="4" fill={marker.color} stroke="var(--color-panel)" strokeWidth="1.5" />}
            </svg>
          </div>;
        })}
        <div className="absolute inset-x-0 bottom-0 flex justify-between text-[10px]" style={{ color: "var(--color-muted)" }}><span>Below Range</span><span>Above Range</span></div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3 border-t pt-4" style={{ borderColor: "var(--color-line-subtle)" }}>
        {summary.map((item) => <div key={item.label} className="min-w-0"><div className="flex items-center gap-1.5 text-[10px]" style={{ color: "var(--color-muted)" }}><i className="h-1.5 w-1.5 shrink-0" style={{ background: item.color, borderRadius: item.shape === "circle" ? "50%" : 1, rotate: item.shape === "diamond" ? "45deg" : undefined }} />{item.label}</div><div className="tnum mt-1 text-sm font-medium text-ink">{displayMoney(item.price)}</div></div>)}
      </div>
    </div>
  );
}
