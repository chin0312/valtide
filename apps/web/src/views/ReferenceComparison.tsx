import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";

// Makes disagreement obvious by plotting every price on an interval-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  const referenceInsideRange = r.reference_under_test != null && r.reference_under_test >= r.fair_value_lower && r.reference_under_test <= r.fair_value_upper;
  return (
    <Panel title="Price Range" icon="range" className="flex-1" right={<span className="font-mono text-[10px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)" }}>Interval View</span>}>
      <p className="mb-3 text-sm font-medium text-ink">{r.reference_under_test == null ? "The tested reference is unavailable." : referenceInsideRange ? "The tested reference is inside the expected range." : "The tested reference is outside the expected range."}</p>
      <ReferenceNumberLine r={r} />
    </Panel>
  );
}
