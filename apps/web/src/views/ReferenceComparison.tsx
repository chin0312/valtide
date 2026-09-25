import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";

// Makes disagreement obvious by plotting every price on an interval-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  return (
    <Panel title="Price map">
      <ReferenceNumberLine r={r} />
    </Panel>
  );
}
