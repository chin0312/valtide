import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";

// Makes disagreement obvious by plotting every price on an interval-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  const referenceInsideRange = r.reference_under_test != null && r.reference_under_test >= r.fair_value_lower && r.reference_under_test <= r.fair_value_upper;
  const comparisonBoundary = r.reference_profile === "xstock_vs_p1ac_challenger"
    ? "Model-based challenger evidence: P1a assimilates this same xStock observation before comparison, so these are not two fully independent observations."
    : r.reference_profile === "legacy_xperp_vs_p1ac"
      ? "Legacy NVDAx profile: the reference under test is the separate OKX X-Perp index."
      : "The reference profile identifies the source and its relationship to the challenger model inputs.";
  return (
    <Panel title="Price Range" icon="range" className="flex-1" right={<span className="font-mono text-[10px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)" }}>Interval View</span>}>
      <p className="mb-3 text-sm font-medium text-ink">{r.reference_under_test == null ? "The tested reference is unavailable." : referenceInsideRange ? "The tested reference is inside the expected range." : "The tested reference is outside the expected range."}</p>
      <p className="mb-3 text-xs text-ink-dim" title={comparisonBoundary}>{comparisonBoundary}</p>
      <ReferenceNumberLine r={r} />
    </Panel>
  );
}
