import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";

// Makes disagreement obvious by plotting every price on an interval-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  const unified = r.validation_target === "xstock_observed_price" || r.reference_profile === "unified_xstock_p1ac_xperp_evidence_v1";
  const target = unified ? r.token_price : r.reference_under_test;
  const targetInsideRange = target != null && target >= r.fair_value_lower && target <= r.fair_value_upper;
  const comparisonBoundary = unified
    ? "Unified v2 evidence: xStock is the validation target, P1a-C is a model-based challenger that has assimilated xStock, and exact-time X-Perp is a separate second-market signal."
    : r.reference_profile === "legacy_xperp_vs_p1ac"
      ? "Legacy NVDAx profile: the reference under test is the separate OKX X-Perp index."
      : "The reference profile identifies the source and its relationship to the challenger model inputs.";
  return (
    <Panel title="Valuation range" icon="range" className="flex-1" right={<span className="font-mono text-[10px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)" }}>Interval view</span>}>
      <p className="mb-3 text-sm font-medium text-ink">{target == null ? `${unified ? "xStock target" : "Reference price"} unavailable.` : targetInsideRange ? `The ${unified ? "xStock target" : "reference"} is within the P1a-C range.` : `The ${unified ? "xStock target" : "reference"} is outside the P1a-C range.`}</p>
      <p className="mb-3 text-xs text-ink-dim" title={comparisonBoundary}>{comparisonBoundary}</p>
      <ReferenceNumberLine r={r} />
    </Panel>
  );
}
