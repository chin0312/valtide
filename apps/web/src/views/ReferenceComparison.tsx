import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";
import { isXStockValidation, validationTargetPrice } from "../lib/semantics";

// Shows the selected observation on a stable price domain from the active timeline window.
export function ReferenceComparison({ r, domainResults = [r] }: { r: ValuationResult; domainResults?: ValuationResult[] }) {
  const targetPrice = validationTargetPrice(r);
  const referenceInsideRange = targetPrice != null && targetPrice >= r.fair_value_lower && targetPrice <= r.fair_value_upper;
  const xstockTarget = isXStockValidation(r);
  return (
    <Panel title="Valuation Range" icon="range" className="flex-1" right={<span className="font-mono text-[10px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)" }}>Range View</span>}>
      <p className="mb-3 text-sm font-medium text-ink">{targetPrice == null ? `${xstockTarget ? "Observed xStock" : "Reference"} price unavailable.` : referenceInsideRange ? `${xstockTarget ? "Observed xStock" : "Reference"} is within the valuation range.` : `${xstockTarget ? "Observed xStock" : "Reference"} is outside the valuation range.`}</p>
      <p className="mb-3 text-[11px] text-muted">Evidence State also considers model disagreement, data quality, and X-Perp confirmation.</p>
      <ReferenceNumberLine r={r} domainResults={domainResults} />
    </Panel>
  );
}
