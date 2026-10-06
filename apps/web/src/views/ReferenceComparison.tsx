import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";
import { isXStockValidation, modelDependenceNote, validationTargetPrice } from "../lib/semantics";

// Makes disagreement obvious by plotting every price on an interval-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  const targetPrice = validationTargetPrice(r);
  const referenceInsideRange = targetPrice != null && targetPrice >= r.fair_value_lower && targetPrice <= r.fair_value_upper;
  const xstockTarget = isXStockValidation(r);
  const comparisonBoundary = modelDependenceNote(r);
  return (
    <Panel title="Valuation Range" icon="range" className="flex-1" right={<span className="font-mono text-[10px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)" }}>Interval View</span>}>
      <p className="mb-3 text-sm font-medium text-ink">{targetPrice == null ? `${xstockTarget ? "Observed xStock" : "Reference"} price unavailable.` : referenceInsideRange ? `${xstockTarget ? "Observed xStock" : "Reference"} is within the valuation range.` : `${xstockTarget ? "Observed xStock" : "Reference"} is outside the valuation range.`}</p>
      <p className="mb-2 text-xs text-ink-dim" title={comparisonBoundary}>{comparisonBoundary}</p>
      <p className="mb-3 text-[11px] text-muted">Interval position is descriptive. Evidence State uses the frozen P1a-C/xStock disagreement band, source-quality checks, and X-Perp corroboration when the signal reaches REVIEW.</p>
      <ReferenceNumberLine r={r} />
    </Panel>
  );
}
