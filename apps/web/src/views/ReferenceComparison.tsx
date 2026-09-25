import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";

// Makes disagreement obvious by plotting every price on an interval-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  return (
    <Panel title="Price range" right={<span className="font-mono text-[9px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)" }}>interval view</span>}>
      <ReferenceNumberLine r={r} />
    </Panel>
  );
}
